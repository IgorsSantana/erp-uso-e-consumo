'use strict';
(() => {
 let itemSequence=0;
 const active=rows=>rows.filter(row=>row.ativo!==false&&row.ativo!==0);
 const statusBadge=status=>status==='Recebida'?'<span class="badge badge-success">Recebida</span>':App.badge(status);
 const ensureManager=()=>{if(!App.canManage)throw new Error('Ordens de compra estão disponíveis para gestores e administradores.');};
 const lineRow=()=>{
  const key=++itemSequence;
  return `<div class="item-row" data-purchase-item><div class="form-field"><label for="purchase-product-${key}">Produto</label><select class="field-control" id="purchase-product-${key}" data-purchase-product required>${App.options(active(Store.produtos).map(p=>({...p,label:p.id+' · '+p.nome+' ('+(p.unidade||'UN')+')'})),'id','label')}</select></div><div class="form-field"><label for="purchase-quantity-${key}">Quantidade</label><input class="field-control" id="purchase-quantity-${key}" data-purchase-quantity type="number" min="0.001" max="999999999" step="0.001" value="1" required></div><div class="form-field"><label for="purchase-cost-${key}">Custo unit. R$</label><input class="field-control" id="purchase-cost-${key}" data-purchase-cost type="number" min="0" max="999999999" step="0.0001" value="0" required></div>${App.button('Remover','remove-purchase-item','type="button" aria-label="Remover produto da ordem"','danger')}</div>`;
 };
 const updateTotal=()=>{
  const form=document.getElementById('dialog-form'),total=document.getElementById('purchase-total');if(!form||!total)return;
  const value=Array.from(form.querySelectorAll('[data-purchase-item]')).reduce((sum,row)=>sum+(Number(row.querySelector('[data-purchase-quantity]').value)||0)*(Number(row.querySelector('[data-purchase-cost]').value)||0),0);
  total.textContent=H.money(value);
 };
 App.views.compras=async()=>{
  ensureManager();const list=await Store.request('/compras');App.data.compras=list;
  const pending=list.filter(p=>p.status==='Pendente'),pendingTotal=pending.reduce((sum,p)=>sum+Number(p.total||0),0);
  const rows=list.map(p=>App.row([`<span class="cell-title">OC #${E(p.id)}</span><span class="cell-subtitle">${H.date(p.criado_em)}${p.cotacao_id?' · Cotação #'+E(p.cotacao_id):' · Compra avulsa'}</span>`,`<span class="cell-title">${E(p.fornecedor_nome)}</span>`,E(p.loja_nome),statusBadge(p.status),H.number(p.itens?.length||0),`<strong class="numeric">${H.money(p.total)}</strong>`,App.button('Ver ordem','view-purchase',`data-id="${E(p.id)}"`,'secondary')],p.id+' '+p.fornecedor_nome+' '+p.loja_nome+' '+p.status+' '+(p.cotacao_id||'')));
  return App.heading('Compras com controle do início ao fim.','Emita ordens de compra e registre a entrada dos materiais recebidos.',App.button('Exportar CSV','export-purchases','','secondary')+App.button('+ Nova compra','new-purchase'))+`<div class="stats-grid"><article class="stat-card"><span class="stat-label">Ordens aguardando recebimento</span><strong class="stat-value">${H.number(pending.length)}</strong><span class="stat-caption">Confirme o recebimento para atualizar o estoque.</span></article><article class="stat-card"><span class="stat-label">Valor das compras pendentes</span><strong class="stat-value">${H.money(pendingTotal)}</strong><span class="stat-caption">Total previsto nas ordens em aberto.</span></article></div>`+App.panel(list.length+' ordens de compra','Ordens recebidas e canceladas permanecem no histórico.',App.toolbar('Buscar ordem, fornecedor, loja ou situação…')+App.table(['Ordem','Fornecedor','Loja de destino','Situação','Itens','Valor total','Ações'],rows));
 };
 App.actions['new-purchase']=()=>{
  ensureManager();
  if(!active(Store.produtos).length||!active(Store.fornecedores).length||!Store.lojas.length){App.modal('Prepare sua ordem de compra','<p>Cadastre ao menos um produto ativo, um fornecedor ativo e uma loja para emitir ordens de compra.</p><div class="row-actions"><a class="button button-secondary" href="#produtos" data-action="close-dialog">Produtos</a><a class="button button-secondary" href="#fornecedores" data-action="close-dialog">Fornecedores</a><a class="button button-secondary" href="#cadastros" data-action="close-dialog">Lojas</a></div>',null,{readOnly:true});return;}
  const body=`<div class="form-grid">${App.field('fornecedor_id','Fornecedor','select','',{items:active(Store.fornecedores),labelKey:'nome_fantasia',required:true})}${App.field('loja_id','Loja que receberá os materiais','select','',{items:Store.lojas,required:true})}${App.field('observacoes','Observações da compra','textarea','',{maxlength:2000,full:true})}</div><div class="panel-header"><div><h3 class="panel-title">Itens da compra</h3><p class="panel-subtitle">Confira os custos negociados antes de emitir a ordem.</p></div>${App.button('+ Adicionar produto','add-purchase-item','type="button"','secondary')}</div><div class="line-items" id="purchase-items">${lineRow()}</div><div class="totals-bar"><span>Valor total previsto</span><strong id="purchase-total">${H.money(0)}</strong></div><p class="field-hint">A criação da ordem não altera o estoque. Confirme o recebimento quando os materiais chegarem à loja.</p>`;
  const form=App.modal('Nova ordem de compra',body,async(data,form)=>{
   const itens=Array.from(form.querySelectorAll('[data-purchase-item]')).map(row=>({produto_id:row.querySelector('[data-purchase-product]').value,quantidade:Number(row.querySelector('[data-purchase-quantity]').value),custo_unitario:Number(row.querySelector('[data-purchase-cost]').value)}));
   if(!data.fornecedor_id||!data.loja_id)throw new Error('Selecione o fornecedor e a loja de destino.');
   if(!itens.length||itens.length>500)throw new Error('Informe de 1 a 500 produtos.');
   if(itens.some(item=>!item.produto_id||!Number.isFinite(item.quantidade)||item.quantidade<=0||!Number.isFinite(item.custo_unitario)||item.custo_unitario<0))throw new Error('Confira os produtos, quantidades e custos de cada item.');
   if(new Set(itens.map(item=>item.produto_id)).size!==itens.length)throw new Error('Há um produto repetido. Consolide sua quantidade em uma única linha.');
   await Store.request('/compras',{method:'POST',body:{fornecedor_id:Number(data.fornecedor_id),loja_id:Number(data.loja_id),observacoes:data.observacoes.trim(),itens}});
   await App.navigate('compras');H.toast('Ordem de compra criada. Registre o recebimento quando os materiais chegarem.');
  },{wide:true,submit:'Emitir ordem de compra'});
  form.addEventListener('change',event=>{if(event.target.matches('[data-purchase-product]')){const product=Store.produtos.find(p=>String(p.id)===event.target.value);event.target.closest('[data-purchase-item]').querySelector('[data-purchase-cost]').value=product?.custo??0;updateTotal();}});
  form.addEventListener('input',event=>{if(event.target.matches('[data-purchase-quantity], [data-purchase-cost]'))updateTotal();});
 };
 App.actions['add-purchase-item']=()=>{ensureManager();const container=document.getElementById('purchase-items');if(!container)return;if(container.children.length>=500)throw new Error('A ordem aceita no máximo 500 produtos.');container.insertAdjacentHTML('beforeend',lineRow());};
 App.actions['remove-purchase-item']=(_,button)=>{
  ensureManager();const container=button.closest('#purchase-items');if(!container)return;
  if(container.querySelectorAll('[data-purchase-item]').length===1)throw new Error('Mantenha pelo menos um produto na ordem.');
  button.closest('[data-purchase-item]').remove();updateTotal();
 };
 App.actions['view-purchase']=async({id})=>{
  ensureManager();const list=await Store.request('/compras');App.data.compras=list;const order=list.find(p=>String(p.id)===String(id));
  if(!order)throw new Error('Ordem de compra não encontrada. Atualize a listagem.');
  const rows=(order.itens||[]).map(item=>App.row([`<span class="cell-title">${E(item.produto_nome)}</span><span class="cell-subtitle">${E(item.produto_id)}</span>`,`<span class="numeric">${H.number(item.quantidade)}</span>`,`<span class="numeric">${H.unitMoney(item.custo_unitario)}</span>`,`<strong class="numeric">${H.money(Number(item.quantidade)*Number(item.custo_unitario))}</strong>`],item.produto_nome));
  const actions=order.status==='Pendente'?`<div class="row-actions">${App.button('Confirmar recebimento','receive-purchase',`type="button" data-id="${E(order.id)}"`)}${App.button('Cancelar ordem','cancel-purchase',`type="button" data-id="${E(order.id)}"`,'danger')}</div><p class="field-hint">Confirme somente após conferir os materiais. Todos os itens serão adicionados ao estoque da loja de destino em um único recebimento.</p>`:'';
  const body=`<div class="panel-header"><div>${statusBadge(order.status)}<p class="panel-subtitle">Emitida em ${H.date(order.criado_em,true)}${order.recebido_em?' · Recebida em '+H.date(order.recebido_em,true):''}</p></div></div><div class="form-grid"><div class="form-field"><span>Fornecedor</span><strong>${E(order.fornecedor_nome)}</strong></div><div class="form-field"><span>Loja de destino</span><strong>${E(order.loja_nome)}</strong></div><div class="form-field full-width"><span>Origem</span><strong>${order.cotacao_id?'Cotação #'+E(order.cotacao_id):'Compra avulsa'}</strong></div>${order.observacoes?`<div class="form-field full-width"><span>Observações</span><p>${E(order.observacoes)}</p></div>`:''}</div>${App.table(['Produto','Quantidade','Custo unitário','Total'],rows,'purchase-detail')}<div class="totals-bar"><span>Valor total da ordem</span><strong>${H.money(order.total)}</strong></div>${actions}`;
  App.modal('Ordem de compra #'+order.id,body,null,{wide:true,readOnly:true});
 };
 App.actions['receive-purchase']=({id})=>{
  ensureManager();return App.confirm('Confirmar recebimento da ordem #'+id+'?','Todos os itens serão adicionados ao estoque da loja de destino pelos custos desta ordem. Confira quantidades e materiais antes de confirmar. Esta ordem só pode ser recebida uma vez.',async()=>{await Store.request('/compras/'+encodeURIComponent(id)+'/receber',{method:'POST'});await Store.loadCatalogs();await App.navigate('compras');H.toast('Recebimento confirmado e entrada no estoque registrada.');});
 };
 App.actions['cancel-purchase']=({id})=>{
  ensureManager();return App.confirm('Cancelar a ordem #'+id+'?','A ordem será cancelada e não poderá ser recebida. O histórico será preservado.',async()=>{await Store.request('/compras/'+encodeURIComponent(id)+'/cancelar',{method:'POST'});await App.navigate('compras');H.toast('Ordem de compra cancelada.');});
 };
 App.actions['export-purchases']=()=>{
  ensureManager();const rows=[];
  for(const order of App.data.compras||[])for(const item of order.itens||[])rows.push([order.id,order.fornecedor_nome,order.loja_nome,order.status,order.cotacao_id||'',order.criado_em,order.recebido_em||'',item.produto_id,item.produto_nome,item.quantidade,item.custo_unitario,Number(item.quantidade)*Number(item.custo_unitario),order.total,order.observacoes||'']);
  H.csv('compras.csv',['Ordem','Fornecedor','Loja de destino','Situação','Cotação','Criada em','Recebida em','Código do produto','Produto','Quantidade','Custo unitário','Total do item','Total da ordem','Observações'],rows);
 };
})();
