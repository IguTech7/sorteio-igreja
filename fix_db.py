import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'rifa_igreja.settings')
django.setup()

from django.db import connection

cursor = connection.cursor()
cursor.execute("ALTER TABLE rifa_registrocomprovante ADD COLUMN IF NOT EXISTS hash_imagem VARCHAR(64) DEFAULT '';")
cursor.execute("ALTER TABLE rifa_registrocomprovante ADD COLUMN IF NOT EXISTS assinatura_transacao VARCHAR(200) DEFAULT '';")
print("Colunas adicionadas com sucesso!")