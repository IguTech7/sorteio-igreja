import json
from django.shortcuts import render
from django.http import JsonResponse
from django.db.models import Q
import mercadopago
# Certifique-se de importar seus modelos corretamente aqui:
from .models import Configuracao, Participante 

# ── VIEW PRINCIPAL (INDEX) COM PROTEÇÃO CONTRA RESET DE MEMÓRIA ──
def index(request):
    config = Configuracao.objects.first()
    dados_sucesso = None

    # Recupera os cookies seguros salvos antes da ida ao banco
    telefone_pendente = request.COOKIES.get('tel_pendente')
    nome_pendente = request.COOKIES.get('nome_pendente')
    numeros_pendentes = request.COOKIES.get('nums_pendentes')

    if telefone_pendente and numeros_pendentes:
        try:
            lista_nums = json.loads(numeros_pendentes)
            # Verifica se o Webhook já processou o pagamento desses números no Supabase
            total_pagos = Participante.objects.filter(numero__in=lista_nums, telefone=telefone_pendente).count()
            
            if total_pagos >= len(lista_nums) and len(lista_nums) > 0:
                dados_sucesso = {
                    'nome': nome_pendente,
                    'numeros': lista_nums
                }
        except Exception as e:
            print(f"Erro ao verificar sucesso no recarregamento: {e}")

    context = {
        'config': config,
        'dados_sucesso': json.dumps(dados_sucesso) if dados_sucesso else 'null'
    }
    
    response = render(request, 'rifa/index.html', context)
    return response


# ── API CRIAR PAGAMENTO (SALVA OS COOKIES POR 10 MINUTOS) ──
def api_criar_pagamento(request):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'erro': 'Método inválido.'}, status=400)
        
    try:
        data = json.loads(request.body)
        selected_nums = data.get('numeros', [])
        nome = data.get('nome', '').strip()
        telefone = data.get('telefone', '').strip()
        
        if not selected_nums or not nome:
            return JsonResponse({'ok': False, 'erro': 'Dados incompletos.'})

        config = Configuracao.objects.first()
        valor_total = len(selected_nums) * float(config.valor)

        # Configuração do Mercado Pago com seu Token Real
        sdk = mercadopago.SDK("APP_USR-242040633012282-062820-b822253c504552aca25d5a971058180b-2914373519")
        request_options = mercadopago.config.RequestOptions()
        request_options.access_token = "APP_USR-242040633012282-062820-b822253c504552aca25d5a971058180b-2914373519"

        payment_data = {
            "transaction_amount": valor_total,
            "description": f"Rifa {config.nome_campanha} - Números: {', '.join(map(str, selected_nums))}",
            "payment_method_id": "pix",
            "payer": {
                "email": "igreja_guararapes@test.com",
                "first_name": nome,
                "phone": {"number": telefone}
            }
        }

        payment_response = sdk.payment().create(payment_data, request_options)
        payment = payment_response["response"]

        if "point_of_interaction" in payment:
            qr_code = payment["point_of_interaction"]["transaction_data"]["qr_code"]
            qr_code_base64 = payment["point_of_interaction"]["transaction_data"]["qr_code_base64"]
            
            # RESPOSTA DO SUCESSO: injeta os cookies de recuperação por 10 minutos (600 segundos)
            response = JsonResponse({
                'ok': True,
                'qr_code': qr_code,
                'qr_code_base64': qr_code_base64
            })
            response.set_cookie('tel_pendente', telefone, max_age=600, path='/')
            response.set_cookie('nome_pendente', nome, max_age=600, path='/')
            response.set_cookie('nums_pendentes', json.dumps(selected_nums), max_age=600, path='/')
            return response
        else:
            return JsonResponse({'ok': False, 'erro': payment.get('message', 'Erro desconhecido na API do MP.')})

    except Exception as e:
        return JsonResponse({'ok': False, 'erro': str(e)})


# ── API VERIFICAR COMPROVANTE (CONSULTA LIMPA E ROBUSTA) ──
def api_verificar_comprovante(request):
    numeros_str = request.GET.get('numeros', '')
    if not numeros_str:
        return JsonResponse({'pago': False})

    try:
        lista_numeros = [int(n.strip()) for n in numeros_str.split(',') if n.strip().isdigit()]
        if not lista_numeros:
            return JsonResponse({'pago': False})

        total_pagos = Participante.objects.filter(numero__in=lista_numeros).count()

        if total_pagos >= len(lista_numeros):
            return JsonResponse({'pago': True})
            
    except Exception as e:
        print(f"Erro na verificação do Pix: {str(e)}")

    return JsonResponse({'pago': False})


# ── OUTRAS APIS DO SISTEMA (MANTENHA SUAS IMPLEMENTAÇÕES ORIGINAIS) ──
def api_status(request):
    # Sua lógica para retornar vendidos, disponíveis e arrecadado
    pass

def api_vendidos(request):
    pass

def api_sortear(request):
    pass

def api_resetar(request):
    pass

def qrcode_pix(request):
    pass

def api_excluir(request):
    pass

def api_registrar_comprovante(request):
    pass

def api_comprovantes(request):
    pass

def api_excluir_comprovante(request):
    pass

def api_editar_comprovante(request):
    pass

def api_registrar_tentativa(request):
    pass

def api_tentativas(request):
    pass

def api_excluir_tentativa(request):
    pass

def api_participar_admin(request):
    pass

def api_webhook_mp(request):
    # Certifique-se de atualizar o token aqui dentro também!
    pass

def api_buscar_participante(request):
    if not request.user.is_authenticated:
        return JsonResponse({'ok': False, 'erro': 'Não autorizado.'}, status=403)
    termo = request.GET.get('termo', '').strip()
    if not termo:
        return JsonResponse({'ok': False, 'participantes': []})
    if termo.isdigit():
        participantes_qs = Participante.objects.filter(numero=int(termo))
    else:
        participantes_qs = Participante.objects.filter(nome__icontains=termo)
    lista_participantes = [{'id': p.id, 'numero': p.numero, 'nome': p.nome, 'telefone': p.telefone} for p in participantes_qs]
    return JsonResponse({'ok': True, 'participantes': lista_participantes})