data = open('backup_rifa.json', 'rb').read()
text = data.decode('utf-8', errors='replace')
open('backup_rifa_clean.json', 'w', encoding='utf-8').write(text)
print('Feito!')