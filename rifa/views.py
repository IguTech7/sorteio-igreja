import os
import random
import io
import qrcode
import mercadopago
from django.db import IntegrityError, transaction
from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import csrf_exempt
import json
from zoneinfo import ZoneInfo
from django.db.models import Q

from .models import Participante, Configuracao, Sorteio, RegistroComprovante

import requests as req_http

def enviar_telegram(mensagem):
    token = os.environ.get('TELEGRAM_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    if not token or not chat_id:
        return
    try:
        req_http.post(
            f'https://api.telegram.org/bot{token}/sendMessage',
            # CORRIGIDO: mudado de 'text': message para 'text': mensagem
            json={'chat_id': chat_id, 'text': mensagem, 'parse_mode': 'HTML'}
        )
    except:
        pass


# ── CORRIGIDO: INDEX AGORA VALIDA E ENVIA OS COOKIES DE RECUPERAÇÃO PARA O TEMPLATE ──
def index(request):
    config = Configuracao.objects.first()
    dados_sucesso = None

    # Verifica se o navegador possui o cookie de que uma compra foi tentada
    telefone_pendente = request.COOKIES.get('tel_pendente')
    nome_pendente = request.COOKIES.get('nome_pendente')
    numeros_pendentes = request.COOKIES.get('nums_pendentes')

    if telefone_pendente and numeros_pendentes:
        try:
            lista_nums = json.loads(numeros_pendentes)
            # Verifica se esses números foram salvos no Supabase recentemente
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


@require_GET
def api_status(request):
    config = Configuracao.get()
    participantes = Participante.objects.all()
    ocupados = {p.numero: p.nome for p in participantes}
    vendidos = participantes.count()
    return JsonResponse({
        'ocupados': ocupados,
        'vendidos': vendidos,
        'disponiveis': config.total_numeros - vendidos,
        'arrecadado': float(config.valor * vendidos),
        'valor': float(config.valor),
        'total_numeros': config.total_numeros,
    })


@csrf_exempt
@require_POST
def api_participar(request):
    try:
        data = json.loads(request.body)
        numeros = data.get('numeros', [])
        nome = data.get('nome', '').strip()
        telefone = data.get('telefone', '').strip()
    except:
        return JsonResponse({'ok': False, 'erro': 'Dados inválidos.'}, status=400)

    config = Configuracao.get()

    if not nome:
        return JsonResponse({'ok': False, 'erro': 'Nome é obrigatório.'}, status=400)
    if not numeros:
        return JsonResponse({'ok': False, 'erro': 'Selecione ao menos um número.'}, status=400)

    try:
        with transaction.atomic():
            for numero in numeros:
                numero = int(numero)
                if numero < 1 or numero > config.total_numeros:
                    return JsonResponse({'ok': False, 'erro': f'Número {numero} inválido.'}, status=400)
                if Participante.objects.filter(numero=numero).exists():
                    return JsonResponse({'ok': False, 'erro': f'O número {numero} já está ocupado.'}, status=409)
            for numero in numeros:
                Participante.objects.create(numero=numero, nome=nome, telefone=telefone)
    except IntegrityError:
        return JsonResponse({'ok': False, 'erro': 'Um ou mais números já foram reservados.'}, status=409)
    
    mensagem = f"🎟 <b>Nova participação!</b>\n\n👤 <b>Nome:</b> {nome}\n📱 <b>Telefone:</b> {telefone or '—'}\n🔢 <b>Números:</b> {', '.join(str(n) for n in numeros)}\n💰 <b>Total:</b> R$ {len(numeros) * 50:.2f}"
    enviar_telegram(mensagem)

    return JsonResponse({'ok': True, 'mensagem': f'{len(numeros)} número(s) confirmado(s) para {nome}!'})


@require_GET
def api_vendidos(request):
    participantes = Participante.objects.all()
    data = [{'numero': p.numero, 'nome': p.nome} for p in participantes]
    return JsonResponse({'vendidos': data})


@csrf_exempt
@require_POST
def api_sortear(request):
    if not request.user.is_authenticated:
        return JsonResponse({'ok': False, 'erro': 'Não autorizado.'}, status=401)
    participantes = list(Participante.objects.all())
    if not participantes:
        return JsonResponse({'ok': False, 'erro': 'Nenhum número vendido para sortear.'}, status=400)
    vencedor = random.choice(participantes)
    Sorteio.objects.create(numero_vencedor=vencedor.numero, nome_vencedor=vencedor.nome)
    return JsonResponse({'ok': True, 'numero': vencedor.numero, 'nome': vencedor.nome})


@csrf_exempt
@require_POST
def api_resetar(request):
    if not request.user.is_authenticated:
        return JsonResponse({'ok': False, 'erro': 'Não autorizado.'}, status=401)
    Participante.objects.all().delete()
    Sorteio.objects.all().delete()
    return JsonResponse({'ok': True, 'mensagem': 'Rifa resetada com sucesso.'})


@require_GET
def qrcode_pix(request):
    config = Configuracao.get()
    dado = config.pix_emv.strip() if config.pix_emv.strip() else config.pix_chave
    img = qrcode.make(dado)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return HttpResponse(buf, content_type='image/png')


@csrf_exempt
@require_POST
def api_excluir(request):
    if not request.user.is_authenticated:
        return JsonResponse({'ok': False, 'erro': 'Não autorizado.'}, status=401)
    try:
        data = json.loads(request.body)
        numero = int(data.get('numero', 0))
    except (ValueError, KeyError):
        return JsonResponse({'ok': False, 'erro': 'Dados inválidos.'}, status=400)
    try:
        p = Participante.objects.get(numero=numero)
        nome = p.nome
        p.delete()
        return JsonResponse({'ok': True, 'mensagem': f'Número {numero} de {nome} removido.'})
    except Participante.DoesNotExist:
        return JsonResponse({'ok': False, 'erro': 'Número não encontrado.'}, status=404)


@csrf_exempt
@require_POST
def api_registrar_comprovante(request):
    try:
        nome_participante = request.POST.get('nome_participante', '').strip()
        pagador = request.POST.get('pagador', '').strip()
        data_hora_pix = request.POST.get('data_hora_pix', '').strip()
        valor = request.POST.get('valor', 0)
        texto_ocr = request.POST.get('texto_ocr', '').strip()
        hash_imagem = request.POST.get('hash_imagem', '').strip()
        assinatura = request.POST.get('assinatura', '').strip()
        imagem = request.FILES.get('imagem')

        if hash_imagem and RegistroComprovante.objects.filter(hash_imagem=hash_imagem).exists():
            return JsonResponse({'ok': False, 'erro': 'Comprovante já utilizado.'})

        if assinatura and RegistroComprovante.objects.filter(assinatura=assinatura).exists():
            return JsonResponse({'ok': False, 'erro': 'Comprovante já utilizado.'})

        RegistroComprovante.objects.create(
            nome_participante=nome_participante,
            pagador=pagador,
            data_hora_pix=data_hora_pix,
            valor=valor,
            texto_ocr=texto_ocr,
            imagem=imagem,
            hash_imagem=hash_imagem,
            assinatura=assinatura,
        )
        return JsonResponse({'ok': True})
    except Exception as e:
        return JsonResponse({'ok': False, 'erro': str(e)}, status=400)


@require_GET
def api_comprovantes(request):
    if not request.user.is_authenticated:
        return JsonResponse({'ok': False, 'erro': 'Não autorizado.'}, status=401)
    registros = RegistroComprovante.objects.all().order_by('-criado_em')
    data = []
    for r in registros:
        numeros = list(Participante.objects.filter(
            nome__icontains=r.nome_participante
        ).values_list('numero', flat=True).order_by('numero'))
        data.append({
            'id': r.id,
            'pagador': r.pagador,
            'data_hora_pix': r.data_hora_pix,
            'valor': float(r.valor),
            'nome_participante': r.nome_participante,
            'criado_em': r.criado_em.astimezone(ZoneInfo('America/Recife')).strftime('%d/%m/%Y %H:%M'),
            'imagem_url': r.imagem.url if r.imagem else None,
            'numeros': numeros,
            'hash_imagem': r.hash_imagem,
        })
    return JsonResponse({'comprovantes': data})


@csrf_exempt
@require_POST
def api_excluir_comprovante(request):
    if not request.user.is_authenticated:
        return JsonResponse({'ok': False, 'erro': 'Não autorizado.'}, status=401)
    try:
        data = json.loads(request.body)
        reg_id = int(data.get('id', 0))
    except:
        return JsonResponse({'ok': False, 'erro': 'Dados inválidos.'}, status=400)
    try:
        r = RegistroComprovante.objects.get(id=reg_id)
        r.delete()
        return JsonResponse({'ok': True})
    except RegistroComprovante.DoesNotExist:
        return JsonResponse({'ok': False, 'erro': 'Registro não encontrado.'}, status=404)


@csrf_exempt
@require_POST
def api_editar_comprovante(request):
    if not request.user.is_authenticated:
        return JsonResponse({'ok': False, 'erro': 'Não autorizado.'}, status=401)
    try:
        data = json.loads(request.body)
        reg_id = int(data.get('id', 0))
        r = RegistroComprovante.objects.get(id=reg_id)
        r.pagador = data.get('pagador', r.pagador).strip()
        r.data_hora_pix = data.get('data_hora_pix', r.data_hora_pix).strip()
        r.nome_participante = data.get('nome_participante', r.nome_participante).strip()
        r.save()
        return JsonResponse({'ok': True})
    except RegistroComprovante.DoesNotExist:
        return JsonResponse({'ok': False, 'erro': 'Registro não encontrado.'}, status=404)
    except Exception as e:
        return JsonResponse({'ok': False, 'erro': str(e)}, status=400)


@csrf_exempt
@require_POST
def api_registrar_tentativa(request):
    try:
        motivo = request.POST.get('motivo', '').strip()
        score = request.POST.get('score', 0)
        aprovado = request.POST.get('aprovado', 'false') == 'true'
        texto_ocr = request.POST.get('texto_ocr', '').strip()
        imagem = request.FILES.get('imagem')

        from .models import TentativaComprovante
        TentativaComprovante.objects.create(
            motivo=motivo,
            score=score,
            aprovado=aprovado,
            texto_ocr=texto_ocr,
            imagem=imagem
        )
        return JsonResponse({'ok': True})
    except Exception as e:
        return JsonResponse({'ok': False, 'erro': str(e)}, status=400)


@require_GET
def api_tentativas(request):
    if not request.user.is_authenticated:
        return JsonResponse({'ok': False, 'erro': 'Não autorizado.'}, status=401)
    from .models import TentativaComprovante
    registros = TentativaComprovante.objects.all().order_by('-data_hora')[:50]
    data = [{
        'id': r.id,
        'data_hora': r.data_hora.astimezone(ZoneInfo('America/Recife')).strftime('%d/%m/%Y %H:%M'),
        'motivo': r.motivo,
        'score': r.score,
        'aprovado': r.aprovado,
        'imagem_url': r.imagem.url if r.imagem else None,
    } for r in registros]
    return JsonResponse({'tentativas': data})


@csrf_exempt
@require_POST
def api_excluir_tentativa(request):
    if not request.user.is_authenticated:
        return JsonResponse({'ok': False, 'erro': 'Não autorizado.'}, status=401)
    try:
        data = json.loads(request.body)
        id = data.get('id')
        from .models import TentativaComprovante
        TentativaComprovante.objects.filter(id=id).delete()
        return JsonResponse({'ok': True})
    except Exception as e:
        return JsonResponse({'ok': False, 'erro': str(e)}, status=400)


@csrf_exempt
@require_POST
def api_participar_admin(request):
    if not request.user.is_authenticated:
        return JsonResponse({'ok': False, 'erro': 'Não autorizado.'}, status=401)
    try:
        data = json.loads(request.body)
        numeros = data.get('numeros', [])
        nome = data.get('nome', '').strip()
        telefone = data.get('telefone', '').strip()
    except:
        return JsonResponse({'ok': False, 'erro': 'Dados inválidos.'}, status=400)

    if not nome or not numeros:
        return JsonResponse({'ok': False, 'erro': 'Nome e números são obrigatórios.'}, status=400)

    erros = []
    salvos = []
    for numero in numeros:
        if Participante.objects.filter(numero=numero).exists():
            erros.append(numero)
        else:
            Participante.objects.create(numero=numero, nome=nome, telefone=telefone)
            salvos.append(numero)

    if erros:
        return JsonResponse({'ok': False, 'erro': f'Números já ocupados: {erros}. Salvos: {salvos}'})
    return JsonResponse({'ok': True, 'mensagem': f'Números {salvos} cadastrados para {nome}!'})


# ── CORRIGIDO: EMBUTE OS COOKIES DE RECUPERAÇÃO NA CRIAÇÃO DO PAGAMENTO PIX REAL ──
@csrf_exempt
@require_POST
def api_criar_pagamento(request):
    try:
        data = json.loads(request.body)
        numeros = data.get('numeros', [])
        nome = data.get('nome', '').strip()
        telefone = data.get('telefone', '').strip()
        
        config = Configuracao.get()
        valor_total = float(len(numeros) * config.valor)
    except:
        return JsonResponse({'ok': False, 'erro': 'Dados inválidos.'}, status=400)

    if not nome or not numeros:
        return JsonResponse({'ok': False, 'erro': 'Nome e números são obrigatórios.'}, status=400)

    sdk = mercadopago.SDK("APP_USR-242040633012282-062820-b822253c504552aca25d5a971058180b-2914373519")

    request_options = mercadopago.config.RequestOptions()
    request_options.access_token = "APP_USR-242040633012282-062820-b822253c504552aca25d5a971058180b-2914373519"

    lista_nome = nome.split()
    primeiro_nome = lista_nome[0] if lista_nome else "Participante"
    ultimo_nome = lista_nome[-1] if len(lista_nome) > 1 else "Silva"

    numeros_str = ','.join(map(str, numeros))
    external_reference = f"{nome}|{numeros_str}|{telefone}"

    payment_data = {
        "transaction_amount": valor_total,
        "description": f"Rifa Igreja - Qtd: {len(numeros)}",
        "payment_method_id": "pix",
        "external_reference": external_reference,
        "notification_url": "https://sorteio-igreja.onrender.com/api/webhook-mp/",
        "payer": {
            "email": f"{primeiro_nome.lower()}@sorteioigreja.com.br",
            "first_name": primeiro_nome,
            "last_name": ultimo_nome
        }
    }

    payment_response = sdk.payment().create(payment_data, request_options)
    payment = payment_response["response"]

    if payment_response["status"] == 201:
        transaction_data = payment["point_of_interaction"]["transaction_data"]
        
        # Resposta acoplando os Cookies de Segurança por 10 minutos (600 segundos)
        response = JsonResponse({
            'ok': True,
            'qr_code': transaction_data['qr_code'],
            'qr_code_base64': transaction_data['qr_code_base64']
        })
        response.set_cookie('tel_pendente', telefone, max_age=600, path='/')
        response.set_cookie('nome_pendente', nome, max_age=600, path='/')
        response.set_cookie('nums_pendentes', numeros_str, max_age=600, path='/')
        return response
    else:
        erro_msg = payment.get('message', 'Erro ao gerar PIX no Mercado Pago.')
        return JsonResponse({'ok': False, 'erro': erro_msg}, status=400)


@csrf_exempt
def api_webhook_mp(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            if data.get('type') == 'payment' or 'payment' in data.get('action', ''):
                payment_id = data['data']['id']
                
                sdk = mercadopago.SDK("APP_USR-242040633012282-062820-b822253c504552aca25d5a971058180b-2914373519")
                
                request_options = mercadopago.config.RequestOptions()
                request_options.access_token = "APP_USR-242040633012282-062820-b822253c504552aca25d5a971058180b-2914373519"
                
                payment = sdk.payment().get(payment_id, request_options)
                payment_info = payment['response']

                if payment_info.get('status') == 'approved':
                    external_ref = payment_info.get('external_reference', '')
                    partes = external_ref.split('|')
                    
                    if len(partes) >= 2:
                        nome = partes[0]
                        numeros = [int(n) for n in partes[1].split(',') if n]
                        telefone = partes[2] if len(partes) > 2 else ''

                        with transaction.atomic():
                            for numero in numeros:
                                if not Participante.objects.filter(numero=numero).exists():
                                    Participante.objects.create(
                                        numero=numero,
                                        nome=nome,
                                        telefone=telefone
                                    )
                                    
                        try:
                            mensagem = f"⚡ <b>Rifa Confirmada Automaticamente!</b>\n\n👤 <b>Nome:</b> {nome}\n📱 <b>Telefone:</b> {telefone or '—'}\n🔢 <b>Número(s) Liberado(s):</b> {', '.join(str(n) for n in numeros)}"
                            enviar_telegram(mensagem)
                        except:
                            pass
                            
        except Exception as e:
            print(f"Webhook erro: {e}")

    return JsonResponse({'ok': True}, status=200)


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

    lista_participantes = []
    for p in participantes_qs:
        lista_participantes.append({
            'id': p.id,
            'numero': p.numero,
            'nome': p.nome,
            'telefone': p.telefone
        })

    return JsonResponse({'ok': True, 'participantes': lista_participantes})


def api_verificar_comprovante(request):
    numeros_str = request.GET.get('numeros', '')
    if not numeros_str:
        return JsonResponse({'pago': False})

    try:
        lista_numeros = [int(n) for n in numeros_str.split(',') if n.strip().isdigit()]
        total_pagos = Participante.objects.filter(numero__in=lista_numeros).count()

        if total_pagos >= len(lista_numeros) and len(lista_numeros) > 0:
            return JsonResponse({'pago': True})
            
    except Exception as e:
        print(f"Erro na verificação do Pix: {str(e)}")

    return JsonResponse({'pago': False})