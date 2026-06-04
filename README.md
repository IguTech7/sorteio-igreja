# Rifa Beneficente - Igreja

Sistema de rifa online desenvolvido com Django + SQLite.

## Como rodar

### 1. Instalar dependências
```bash
pip install -r requirements.txt
```

### 2. Aplicar o banco de dados
```bash
python manage.py migrate
```

### 3. Criar superusuário (para o painel admin)
```bash
python manage.py createsuperuser
```

### 4. Rodar o servidor
```bash
python manage.py runserver
```

Acesse: http://127.0.0.1:8000

## Painel Administrativo

Acesse http://127.0.0.1:8000/admin para:
- Configurar nome da campanha, chave PIX, valor, data do sorteio
- Ver todos os participantes
- Consultar histórico de sorteios

## Personalizar a rifa

No painel admin, edite o objeto **Configuracao** com:
- Nome da campanha
- Subtítulo
- Valor por número
- Data do sorteio
- Prêmio
- Chave PIX
- Total de números (padrão: 100)

## Estrutura de arquivos

```
rifa_igreja/
├── manage.py
├── requirements.txt
├── db.sqlite3              ← banco de dados (gerado automaticamente)
├── rifa_igreja/
│   ├── settings.py
│   └── urls.py
└── rifa/
    ├── models.py           ← Participante, Configuracao, Sorteio
    ├── views.py            ← lógica e API
    ├── urls.py             ← rotas
    ├── admin.py            ← painel admin
    └── templates/
        └── rifa/
            └── index.html  ← interface completa
```

## Rotas da API

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/api/status/` | Retorna ocupados, vendidos, arrecadado |
| POST | `/api/participar/` | Registra participante |
| GET | `/api/vendidos/` | Lista todos os vendidos |
| POST | `/api/sortear/` | Realiza o sorteio |
| POST | `/api/resetar/` | Apaga todos os registros |
