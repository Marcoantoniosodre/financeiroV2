import hashlib
import hmac
import secrets
from datetime import date
from pathlib import Path

import firebase_admin
import streamlit as st
from firebase_admin import credentials, firestore
from google.api_core.exceptions import AlreadyExists, GoogleAPICallError


st.set_page_config(page_title="Gestão Financeira", page_icon="💰", layout="wide")

SERVICE_ACCOUNT_FILE = (
    Path(__file__).resolve().parent
    / "financeiro-b0c58-firebase-adminsdk-fbsvc-04f0310bd8.json"
)
PASSWORD_ITERATIONS = 600_000
CATEGORIES = [
    "Alimentação",
    "Moradia",
    "Transporte",
    "Saúde",
    "Educação",
    "Lazer",
    "Salário",
    "Investimentos",
    "Outros",
]


@st.cache_resource
def get_database():
    if not SERVICE_ACCOUNT_FILE.is_file():
        raise FileNotFoundError(
            f"Arquivo de credenciais não encontrado: {SERVICE_ACCOUNT_FILE.name}"
        )

    try:
        app = firebase_admin.get_app()
    except ValueError:
        app = firebase_admin.initialize_app(
            credentials.Certificate(str(SERVICE_ACCOUNT_FILE))
        )
    return firestore.client(app=app)


def password_hash(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS
    )


def user_document_id(email: str) -> str:
    return hashlib.sha256(email.encode("utf-8")).hexdigest()


def normalize_email(email: str) -> str:
    return email.strip().lower()


def show_authentication(db):
    st.title("💰 Gestão Financeira")
    st.caption("Organize suas receitas e despesas com segurança.")
    login_tab, register_tab = st.tabs(["Entrar", "Criar conta"])

    with login_tab:
        with st.form("login_form"):
            email = st.text_input("E-mail", autocomplete="email")
            password = st.text_input(
                "Senha", type="password", autocomplete="current-password"
            )
            submitted = st.form_submit_button("Entrar", type="primary")

        if submitted:
            normalized_email = normalize_email(email)
            if not normalized_email or not password:
                st.error("Informe o e-mail e a senha.")
            else:
                try:
                    user_ref = db.collection("usuarios").document(
                        user_document_id(normalized_email)
                    )
                    user = user_ref.get()
                    if user.exists:
                        user_data = user.to_dict()
                        salt = bytes.fromhex(user_data["salt"])
                        expected_hash = bytes.fromhex(user_data["password_hash"])
                    else:
                        salt = bytes(16)
                        expected_hash = password_hash(password, salt)

                    if user.exists and hmac.compare_digest(
                        password_hash(password, salt), expected_hash
                    ):
                        st.session_state["user"] = {
                            "id": user.id,
                            "email": normalized_email,
                        }
                        st.rerun()
                    else:
                        st.error("E-mail ou senha inválidos.")
                except (GoogleAPICallError, KeyError, ValueError) as error:
                    st.error(f"Não foi possível entrar: {error}")

    with register_tab:
        with st.form("register_form"):
            email = st.text_input("E-mail", key="register_email")
            password = st.text_input(
                "Senha (mínimo de 8 caracteres)",
                type="password",
                key="register_password",
            )
            password_confirmation = st.text_input(
                "Confirme a senha",
                type="password",
                key="register_password_confirmation",
            )
            submitted = st.form_submit_button("Criar conta", type="primary")

        if submitted:
            normalized_email = normalize_email(email)
            if "@" not in normalized_email or "." not in normalized_email.rsplit("@", 1)[-1]:
                st.error("Informe um e-mail válido.")
            elif len(password) < 8:
                st.error("A senha deve ter pelo menos 8 caracteres.")
            elif password != password_confirmation:
                st.error("As senhas não conferem.")
            else:
                salt = secrets.token_bytes(16)
                user_ref = db.collection("usuarios").document(
                    user_document_id(normalized_email)
                )
                try:
                    user_ref.create(
                        {
                            "email": normalized_email,
                            "salt": salt.hex(),
                            "password_hash": password_hash(password, salt).hex(),
                        }
                    )
                    st.session_state["user"] = {
                        "id": user_ref.id,
                        "email": normalized_email,
                    }
                    st.rerun()
                except AlreadyExists:
                    st.error("Já existe uma conta cadastrada com esse e-mail.")
                except GoogleAPICallError as error:
                    st.error(f"Não foi possível criar a conta: {error}")


def load_transactions(db, user_id: str) -> list[dict]:
    records = (
        db.collection("lancamentos")
        .where("owner_id", "==", user_id)
        .stream()
    )
    transactions = []
    for record in records:
        transaction = record.to_dict()
        transaction["id"] = record.id
        transactions.append(transaction)
    return sorted(transactions, key=lambda item: item["date"], reverse=True)


def render_dashboard(db, user: dict):
    st.title("💰 Gestão Financeira")
    st.caption(f"Conectado como {user['email']}")
    if st.button("Sair"):
        del st.session_state["user"]
        st.rerun()

    try:
        transactions = load_transactions(db, user["id"])
    except GoogleAPICallError as error:
        st.error(f"Não foi possível carregar os lançamentos: {error}")
        return

    income_cents = sum(
        item["amount_cents"] for item in transactions if item["type"] == "Receita"
    )
    expense_cents = sum(
        item["amount_cents"] for item in transactions if item["type"] == "Despesa"
    )
    balance_cents = income_cents - expense_cents
    metric_columns = st.columns(3)
    metric_columns[0].metric("Receitas", f"R$ {income_cents / 100:,.2f}")
    metric_columns[1].metric("Despesas", f"R$ {expense_cents / 100:,.2f}")
    metric_columns[2].metric("Saldo", f"R$ {balance_cents / 100:,.2f}")

    add_tab, manage_tab = st.tabs(["Novo lançamento", "Gerenciar lançamentos"])
    with add_tab:
        with st.form("create_transaction_form", clear_on_submit=True):
            transaction_type = st.selectbox("Tipo", ["Despesa", "Receita"])
            description = st.text_input("Descrição")
            category = st.selectbox("Categoria", CATEGORIES)
            amount = st.number_input(
                "Valor (R$)", min_value=0.01, step=1.00, format="%.2f"
            )
            transaction_date = st.date_input("Data", value=date.today())
            submitted = st.form_submit_button("Salvar lançamento", type="primary")

        if submitted:
            if not description.strip():
                st.error("Informe uma descrição.")
            else:
                try:
                    db.collection("lancamentos").add(
                        {
                            "owner_id": user["id"],
                            "type": transaction_type,
                            "description": description.strip(),
                            "category": category,
                            "amount_cents": round(amount * 100),
                            "date": transaction_date.isoformat(),
                        }
                    )
                    st.success("Lançamento salvo.")
                    st.rerun()
                except GoogleAPICallError as error:
                    st.error(f"Não foi possível salvar o lançamento: {error}")

    with manage_tab:
        if not transactions:
            st.info("Você ainda não tem lançamentos.")
        else:
            st.subheader("Lançamentos")
            st.dataframe(
                [
                    {
                        "Data": item["date"],
                        "Tipo": item["type"],
                        "Descrição": item["description"],
                        "Categoria": item["category"],
                        "Valor (R$)": f"{item['amount_cents'] / 100:.2f}",
                    }
                    for item in transactions
                ],
                use_container_width=True,
                hide_index=True,
            )
            options = {item["id"]: item for item in transactions}
            selected_id = st.selectbox(
                "Selecione um lançamento para editar ou excluir",
                options=list(options),
                format_func=lambda record_id: (
                    f"{options[record_id]['date']} · "
                    f"{options[record_id]['type']} · "
                    f"{options[record_id]['description']} · "
                    f"R$ {options[record_id]['amount_cents'] / 100:.2f}"
                ),
            )
            selected = options[selected_id]

            with st.form("edit_transaction_form"):
                edit_type = st.selectbox(
                    "Tipo", ["Despesa", "Receita"],
                    index=["Despesa", "Receita"].index(selected["type"]),
                )
                edit_description = st.text_input(
                    "Descrição", value=selected["description"]
                )
                edit_category = st.selectbox(
                    "Categoria",
                    CATEGORIES,
                    index=CATEGORIES.index(selected["category"])
                    if selected["category"] in CATEGORIES
                    else CATEGORIES.index("Outros"),
                )
                edit_amount = st.number_input(
                    "Valor (R$)",
                    min_value=0.01,
                    value=selected["amount_cents"] / 100,
                    step=1.00,
                    format="%.2f",
                )
                edit_date = st.date_input(
                    "Data",
                    value=date.fromisoformat(selected["date"]),
                    key=f"edit_date_{selected_id}",
                )
                save_changes = st.form_submit_button("Salvar alterações")

            if save_changes:
                if not edit_description.strip():
                    st.error("Informe uma descrição.")
                else:
                    try:
                        db.collection("lancamentos").document(selected_id).update(
                            {
                                "type": edit_type,
                                "description": edit_description.strip(),
                                "category": edit_category,
                                "amount_cents": round(edit_amount * 100),
                                "date": edit_date.isoformat(),
                            }
                        )
                        st.success("Lançamento atualizado.")
                        st.rerun()
                    except GoogleAPICallError as error:
                        st.error(f"Não foi possível atualizar: {error}")

            if st.button("Excluir lançamento selecionado", type="secondary"):
                try:
                    db.collection("lancamentos").document(selected_id).delete()
                    st.success("Lançamento excluído.")
                    st.rerun()
                except GoogleAPICallError as error:
                    st.error(f"Não foi possível excluir: {error}")


try:
    database = get_database()
except (FileNotFoundError, ValueError, firebase_admin.exceptions.FirebaseError) as error:
    st.title("💰 Gestão Financeira")
    st.error(f"Não foi possível conectar ao Firebase: {error}")
    st.info(
        "Confira se o arquivo JSON de credenciais está na pasta do app e "
        "se a conta de serviço tem acesso ao Firestore."
    )
    st.stop()

if "user" not in st.session_state:
    show_authentication(database)
else:
    render_dashboard(database, st.session_state["user"])
