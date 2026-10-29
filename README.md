# Gestão Financeira

Aplicação de gestão financeira feita com Python, Streamlit e Firestore.

## Executar localmente

1. Use Python 3.10 ou superior.
2. O arquivo `.streamlit/secrets.toml` pode ser gerado a partir do JSON com:

   ```powershell
   python gerador_secrets.py
   ```

   Para gerar o arquivo local automaticamente no PowerShell:

   ```powershell
   python -c "from pathlib import Path; import subprocess,sys; r=subprocess.run([sys.executable,'gerador_secrets.py'],capture_output=True,text=True,check=True); d=Path('.streamlit'); d.mkdir(exist_ok=True); (d/'secrets.toml').write_text(r.stdout,encoding='utf-8')"
   ```

   O app usa essa configuração quando existe. Como alternativa local, mantenha o arquivo
   `financeiro-b0c58-firebase-adminsdk-fbsvc-04f0310bd8.json` na pasta do
   projeto. Nunca compartilhe nem versione esses arquivos.
3. Instale as dependências e inicie o app:

   ```powershell
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   streamlit run app.py
   ```

O app usa a conta de serviço do JSON para acessar o banco de dados padrão do
Firestore no projeto Firebase. Essa conta precisa ter permissão para ler e
gravar no Firestore.

## Funcionalidades

- Cadastro e login por e-mail e senha.
- Cadastro, listagem, edição e exclusão de receitas e despesas.
- Resumo de receitas, despesas e saldo.
- Cada lançamento é associado à conta que o criou.

As contas ficam na coleção `usuarios`; os lançamentos ficam em `lancamentos`.
As senhas não são gravadas em texto puro: o app armazena salt e hash PBKDF2
com SHA-256.

> Esta autenticação é própria da aplicação e não substitui Firebase
> Authentication. Para um produto público, prefira Firebase Authentication e
> mantenha a chave privada da conta de serviço exclusivamente no servidor.
