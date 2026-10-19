'use strict';
App.actions['stock-limits']=async({produto,loja})=>{
 if(!App.canManage)throw new Error('Somente gestores e administradores podem alterar os limites.');
 const result=await Store.request(`/produtos/${encodeURIComponent(produto)}/limites`),items=result.lojas;
 const rows=items.map(item=>`<tr data-limit-store="${item.loja_id}"><td><strong>${E(item.loja_nome)}</strong><span class="cell-subtitle">Disponível: ${H.number(item.quantidade)} ${E(result.produto.unidade)}</span></td><td><label class="checkbox-field"><input type="checkbox" data-limit-active aria-label="Usar limites em ${E(item.loja_nome)}" ${item.limites_configurados?'checked':''}>Usar limites</label></td><td><input class="field-control" type="number" min="0" step="0.001" data-limit-min aria-label="Mínimo em ${E(item.loja_nome)}" value="${item.estoque_minimo}" ${item.limites_configurados?'required':'disabled'}></td><td><input class="field-control" type="number" min="0" step="0.001" data-limit-max aria-label="Máximo em ${E(item.loja_nome)}" value="${item.estoque_maximo}" ${item.limites_configurados?'required':'disabled'}></td></tr>`).join('');
 const form=App.modal('Limites de estoque por loja',`<p><strong>${E(result.produto.nome)}</strong> · ${E(result.produto.id)}</p><div class="inline-alert">Cada loja tem seus próprios limites para este produto. Salvar uma loja não altera as outras. Máximo zero significa sem teto; desmarque Usar limites para remover a configuração da loja.</div><div class="table-wrap"><table class="data-table limits-table"><thead><tr><th>Loja / saldo</th><th>Configuração</th><th>Mínimo</th><th>Máximo</th></tr></thead><tbody>${rows}</tbody></table></div>`,async(_data,form)=>{
  const changes=[];
  for(const row of form.querySelectorAll('[data-limit-store]')){
   const previous=items.find(item=>String(item.loja_id)===row.dataset.limitStore);
   const active=row.querySelector('[data-limit-active]').checked,minimum=Number(row.querySelector('[data-limit-min]').value),maximum=Number(row.querySelector('[data-limit-max]').value);
   if(active&&(!Number.isFinite(minimum)||!Number.isFinite(maximum)||minimum<0||maximum<0||(maximum>0&&minimum>maximum)))throw new Error(`Confira os limites de ${previous.loja_nome}. O máximo deve ser maior ou igual ao mínimo, ou zero para deixar sem teto.`);
   if(active!==Boolean(previous.limites_configurados)||(active&&(minimum!==Number(previous.estoque_minimo)||maximum!==Number(previous.estoque_maximo))))changes.push({loja_id:previous.loja_id,configurado:active,estoque_minimo:minimum,estoque_maximo:maximum});
  }
  if(!changes.length){H.toast('Nenhuma configuração foi alterada.');return;}
  await Store.request(`/produtos/${encodeURIComponent(produto)}/limites`,{method:'PUT',body:{lojas:changes}});
  await App.navigate(App.view);H.toast(`Limites atualizados em ${changes.length} loja(s).`);
 },{wide:true,submit:'Salvar limites das lojas'});
 form.addEventListener('change',event=>{if(event.target.matches('[data-limit-active]')){const row=event.target.closest('[data-limit-store]');row.querySelectorAll('[data-limit-min],[data-limit-max]').forEach(input=>{input.disabled=!event.target.checked;input.required=event.target.checked;});}});
 if(loja){const row=form.querySelector(`[data-limit-store="${CSS.escape(String(loja))}"]`);row?.scrollIntoView({block:'nearest'});row?.querySelector('[data-limit-active]')?.focus();}
};
