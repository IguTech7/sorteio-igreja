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
            json={'chat_id': chat_id, 'text': mensagem, 'parse_mode': 'HTML'}
        )
    except:
        pass


def index(request):
    config = Configuracao.get()
    return render(request, 'rifa/index.html', {'config': config})


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



def api_verificar_comprovante(request):
    numeros_str = request.GET.get('numeros', '')
    if not numeros_str:
        return JsonResponse({'pago': False})

    try:
        # Divide por vírgula, limpa espaços vazios e converte estritamente para int
        lista_numeros = [int(n.strip()) for n in numeros_str.split(',') if n.strip().isdigit()]
        
        if not lista_numeros:
            return JsonResponse({'pago': False})

        # Conta quantos desses números já estão associados a um participante no banco
        total_pagos = Participante.objects.filter(numero__in=lista_numeros).count()

        # Se encontrou todos os números salvos no banco, o pagamento foi aprovado!
        if total_pagos >= len(lista_numeros):
            return JsonResponse({'pago': True})
            
    except Exception as e:
        print(f"Erro crítico na verificação do Pix: {str(e)}")

    return JsonResponse({'pago': False})


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

        # Verificar duplicata por hash (mais forte)
        if hash_imagem and RegistroComprovante.objects.filter(hash_imagem=hash_imagem).exists():
            return JsonResponse({'ok': False, 'erro': 'Comprovante já utilizado.'})

        # Verificar duplicata por assinatura (pagador+data+valor)
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

import base64

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

    # 1. Inicializa a SDK com o token de produção oficial
    sdk = mercadopago.SDK("APP_USR-242040633012282-062820-b822253c504552aca25d5a971058180b-2914373519")

    # 2. Configura explicitamente as opções de requisição exigidas pela SDK moderna
    request_options = mercadopago.config.RequestOptions()
    request_options.access_token = "APP_USR-242040633012282-062820-b822253c504552aca25d5a971058180b-2914373519"

    # Tratamento simples do nome para exigências do Mercado Pago
    lista_nome = nome.split()
    primeiro_nome = lista_nome[0] if lista_nome else "Participante"
    ultimo_nome = lista_nome[-1] if len(lista_nome) > 1 else "Silva"

    # String de referência contendo os metadados ("Nome|Números|Telefone")
    numeros_str = ','.join(map(str, numeros))
    external_reference = f"{nome}|{numeros_str}|{telefone}"

    # Payload oficial da Payments API para Pix Nativo
    payment_data = {
        "transaction_amount": valor_total,
        "description": f"Rifa Igreja - Qtd: {len(numeros)}",
        "payment_method_id": "pix",
        "external_reference": external_reference,
        "notification_url": "https://sorteio-igreja.onrender.com/api/webhook-mp/",
        "payer": {
            "email": f"{primeiro_nome.lower()}@sorteioigreja.com.br", # E-mail obrigatório estruturado
            "first_name": primeiro_nome,
            "last_name": ultimo_nome
        }
    }

    # 3. Dispara a criação real no Mercado Pago
    payment_response = sdk.payment().create(payment_data, request_options)
    payment = payment_response["response"]

    if payment_response["status"] == 201:
        transaction_data = payment["point_of_interaction"]["transaction_data"]
        
        return JsonResponse({
            'ok': True,
            'qr_code': transaction_data['qr_code'],
            'qr_code_base64': transaction_data['qr_code_base64']
        })
    else:
        erro_msg = payment.get('message', 'Erro ao gerar PIX no Mercado Pago.')
        return JsonResponse({'ok': False, 'erro': erro_msg}, status=400)
    
@csrf_exempt
def api_webhook_mp(request):
    if request.method == 'POST':
        try:
            # Captura a notificação enviada no body pela rota do Render
            data = json.loads(request.body)
            
            # O Mercado Pago avisa sobre atualizações filtrando por action ou type
            if data.get('type') == 'payment' or 'payment' in data.get('action', ''):
                payment_id = data['data']['id']
                
                # Inicializa a SDK e as opções de requisição para a busca subsequente
                sdk = mercadopago.SDK("APP_USR-242040633012282-062820-b822253c504552aca25d5a971058180b-2914373519")
                
                request_options = mercadopago.config.RequestOptions()
                request_options.access_token = "APP_USR-242040633012282-062820-b822253c504552aca25d5a971058180b-2914373519"
                
                payment = sdk.payment().get(payment_id, request_options)
                payment_info = payment['response']

                # Verifica se o status do pagamento retornou 'approved'
                if payment_info.get('status') == 'approved':
                    external_ref = payment_info.get('external_reference', '')
                    partes = external_ref.split('|')
                    
                    if len(partes) >= 2:
                        nome = partes[0]
                        numeros = [int(n) for n in partes[1].split(',') if n]
                        telefone = partes[2] if len(partes) > 2 else ''

                        # Garante a atomicidade para impedir duplicações no banco de dados da Igreja
                        with transaction.atomic():
                            for numero in numeros:
                                if not Participante.objects.filter(numero=numero).exists():
                                    Participante.objects.create(
                                        numero=numero,
                                        nome=nome,
                                        telefone=telefone
                                    )
                                    
                        # Envia notificação para o grupo do Telegram da Igreja informando o sucesso automático
                        try:
                            mensagem = f"⚡ <b>Rifa Confirmada Automaticamente!</b>\n\n👤 <b>Nome:</b> {nome}\n📱 <b>Telefone:</b> {telefone or '—'}\n🔢 <b>Número(s) Liberado(s):</b> {', '.join(str(n) for n in numeros)}"
                            enviar_telegram(mensagem)
                        except:
                            pass
                            
        except Exception as e:
            print(f"Webhook erro: {e}")

    # Retorna HTTP 200 imediatamente para o Mercado Pago dar o evento por recebido
    return JsonResponse({'ok': True}, status=200)

def api_buscar_participante(request):
    # Verifica se o usuário está logado como administrador
    if not request.user.is_authenticated:
        return JsonResponse({'ok': False, 'erro': 'Não autorizado.'}, status=403)
        
    termo = request.GET.get('termo', '').strip()
    
    if not termo:
        return JsonResponse({'ok': False, 'participantes': []})

    # Busca por número exato ou por parte do nome (case-insensitive)
    if termo.isdigit():
        participantes_qs = Participante.objects.filter(numero=int(termo))
    else:
        participantes_qs = Participante.objects.filter(nome__icontains=termo)

    # Estrutura a lista de resposta que o seu JavaScript espera receber
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
        # Separa a string "1,2" em uma lista de inteiros [1, 2]
        lista_numeros = [int(n) for n in numeros_str.split(',') if n.strip().isdigit()]
        
        # Conta quantos desses números já foram gravados com sucesso na tabela Participante
        # (Lembrando que o seu Webhook do MP cria o participante assim que detecta o pagamento aprovado)
        total_pagos = Participante.objects.filter(numero__in=lista_numeros).count()

        # Se todos os números que a pessoa escolheu já constam no banco, significa que o pagamento foi processado!
        if total_pagos >= len(lista_numeros) and len(lista_numeros) > 0:
            return JsonResponse({'pago': True})
            
    except Exception as e:
        print(f"Erro na verificação do Pix: {str(e)}")

    return JsonResponse({'pago': False})