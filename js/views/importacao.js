'use strict';
(() => {
 const fields=[['id','Código ERP *'],['nome','Nome / descrição *'],['secao','Seção / categoria'],['unidade','Unidade de medida'],['custo','Custo unitário'],['estoque_minimo','Estoque mínimo'],['estoque_maximo','Estoque máximo'],['referencia','Referência'],['marca','Marca'],['destinacao','Destinação de uso'],['periodo_consumo','Período de consumo']];
 const ensureManager=()=>{if(!App.canManage)throw new Error('A importação está disponível para gestores e administradores.');};
 const spreadsheet='https://docs.google.com/spreadsheets/d/1AxzIohRA-dTECypfoHMii6qNN4LlcAcj0LzIynLLN8E/edit?gid=1815952854#gid=1815952854';
 function showError(message){const target=document.getElementById('dialog-error');if(target){target.textContent=message;target.hidden=false;target.scrollIntoView({block:'nearest'});}else H.toast(message,'error');}
 const originalProducts=App.views.produtos;
 App.views.produtos=async()=>{
  const html=await originalProducts();
  if(!App.canManage)return html;
  return html.replace('<div class="page-actions">','<div class="page-actions">'+App.button('Importar planilha','import-products','','secondary'));
 };
 App.actions['import-products']=()=>{
  ensureManager();
  App.modal('Importar produtos da planilha',`<p>Leia uma aba do Google Sheets ou selecione o arquivo Excel ou CSV. Você poderá conferir as colunas e os produtos antes de confirmar.</p><section class="import-source"><h3>Link do Google Sheets</h3>${App.field('sheet_url','Link da planilha','url',spreadsheet,{full:true,hint:'O link precisa permitir a leitura da aba por este ambiente.'})}${App.button('Ler planilha do Google','read-google-sheet','','primary')}</section><section class="import-source"><h3>Arquivo Excel ou CSV</h3><p>O Excel importa todas as abas de produtos, com prioridade para as abas visíveis. Códigos conflitantes são separados para revisão.</p><div class="form-field"><label for="catalog-file">Arquivo de produtos (.xlsx ou .csv)</label><input class="field-control" id="catalog-file" type="file" accept=".xlsx,.csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,text/csv,text/tab-separated-values"></div>${App.button('Conferir arquivo','read-catalog-file','','secondary')}</section><div class="inline-alert">A importação de produtos preserva os saldos físicos. Cadastros existentes são mantidos, a menos que você escolha atualizá-los na etapa de conferência.</div>`,null,{wide:true,readOnly:true});
 };
 async function analyze(source, mapping, headerRow,report=null){
  const analysis=await Store.request('/produtos/importar',{method:'POST',body:{csv_text:source,...(mapping?{mapping,header_row:headerRow}:{})}});
  App.data.catalogImport={source,analysis,report};renderPreview();
 }
 App.actions['read-google-sheet']=async(_,button)=>{
  ensureManager();button.disabled=true;const label=button.textContent;button.textContent='Lendo planilha…';
  try{const result=await Store.request('/produtos/ler-planilha',{method:'POST',body:{url:document.getElementById('field-sheet_url').value}});await analyze(result.csv_text);}
  catch(error){showError(error.message);}
  finally{button.disabled=false;button.textContent=label;}
 };
 App.actions['read-catalog-file']=async(_,button)=>{
  ensureManager();button.disabled=true;
  try{
   const file=document.getElementById('catalog-file').files[0];
   if(!file)throw new Error('Selecione um arquivo Excel (.xlsx) ou CSV.');
   if(file.size>1500000)throw new Error('O arquivo excede o limite de 1,5 MB.');
   if(file.name.toLowerCase().endsWith('.xlsx')){
    const form=new FormData();form.append('arquivo',file);
    const response=await fetch('/api/produtos/ler-excel',{method:'POST',credentials:'same-origin',headers:{'X-CSRF-Token':Store.csrfToken},body:form});
    const result=await response.json();if(!response.ok)throw new Error(result.error||'Não foi possível ler o Excel.');
    await analyze(result.csv_text,undefined,undefined,result.report);return;
   }
   const buffer=await file.arrayBuffer();let source;
   try{source=new TextDecoder('utf-8',{fatal:true}).decode(buffer);}catch{source=new TextDecoder('windows-1252').decode(buffer);}
   await analyze(source);
  }catch(error){showError(error.message);}finally{button.disabled=false;}
 };
 function currentMapping(){
  const result={};document.querySelectorAll('[data-import-field]').forEach(input=>{if(input.value!=='')result[input.dataset.importField]=Number(input.value);});return result;
 }
 function renderPreview(){
  const state=App.data.catalogImport,a=state.analysis;
  const mapping=fields.map(([key,label])=>`<div class="form-field"><label for="import-${key}">${E(label)}</label><select class="field-control" id="import-${key}" data-import-field="${E(key)}"><option value="">Não importar</option>${a.headers.map((header,i)=>`<option value="${i}" ${a.mapping[key]===i?'selected':''}>${i+1}. ${E(header)}</option>`).join('')}</select></div>`).join('');
  const errors=a.errors.length?`<div class="inline-alert danger" role="alert"><div><strong>${a.errors.length} erro(s) para corrigir</strong><ul>${a.errors.slice(0,12).map(error=>`<li>Linha ${E(error.linha)}: ${E(error.mensagem)}</li>`).join('')}</ul>${a.errors.length>12?'<p>Confira as demais linhas no arquivo antes de importar.</p>':''}</div></div>`:'';
  const preview=a.rows.slice(0,10).map(row=>App.row([E(row.id),E(row.nome),E(row.secao||'—'),E(row.unidade||'UN'),row.custo===undefined?'Não informado':H.money(row.custo)]));
  const conflicts=state.report?.conflicts||[];
  const sourceNotice=conflicts.length?`<div class="inline-alert danger"><div><strong>${conflicts.length} código(s) separado(s) para revisão</strong><p>Estes códigos têm descrições diferentes no Excel e não serão importados. O cadastro atual será preservado.</p><ul>${conflicts.map(item=>`<li><strong>${E(item.id)}</strong>: ${item.variants.map(variant=>`${E(variant.nome)} (${E(variant.sheet)}, linha ${E(variant.row)})`).join(' / ')}</li>`).join('')}</ul></div></div>`:'';
  const body=`${sourceNotice}<div class="inline-alert"><div><strong>${a.rows.length} produto(s) válido(s): ${a.novos} novo(s) e ${a.existentes} já cadastrado(s).</strong><p>${a.ignored} linha(s) idêntica(s) repetida(s) desconsiderada(s). Nenhum produto foi gravado ainda.</p></div></div><h3>Associe as colunas</h3><p>Confira especialmente código e descrição. Códigos com zeros à esquerda são mantidos.</p>${App.field('header_row','Linha dos títulos das colunas','number',a.header_row,{min:1,step:1})}<div class="form-grid">${mapping}</div><div class="row-actions">${App.button('Conferir novamente','analyze-catalog','','secondary')}</div>${errors}<h3>Prévia dos primeiros ${Math.min(10,a.rows.length)} produtos</h3>${App.table(['Código','Produto','Seção','Unidade','Custo'],preview,'catalog-preview')}${a.warnings.map(warning=>`<p class="field-hint">${E(warning)}</p>`).join('')}<label class="checkbox-field import-update"><input type="checkbox" name="atualizar_existentes" id="import-update">Atualizar os produtos existentes com as colunas preenchidas nesta planilha.</label><p class="field-hint">Desmarcado: cadastros existentes são preservados. Campos vazios e saldos físicos são mantidos em ambos os casos.</p>`;
  const form=App.modal('Conferir importação de produtos',body,async(_data,form)=>{
   const mapping=currentMapping();
   if(JSON.stringify(Object.entries(mapping).sort())!==JSON.stringify(Object.entries(a.mapping).sort())||Number(form.elements.header_row.value)!==a.header_row)throw new Error('As colunas foram alteradas. Clique em Conferir novamente antes de importar.');
   if(a.errors.length)throw new Error('Corrija os erros indicados e confira novamente.');
   const result=await Store.request('/produtos/importar',{method:'POST',body:{csv_text:state.source,mapping,header_row:a.header_row,aplicar:true,atualizar_existentes:form.elements.atualizar_existentes.checked}});
   await Store.loadCatalogs();await App.navigate('produtos');
   H.toast(`${result.criados} produto(s) criado(s), ${result.atualizados} atualizado(s), ${result.preservados} preservado(s).`);
   App.data.catalogImport=null;
  },{wide:true,submit:'Confirmar importação'});
  const button=form.querySelector('#dialog-submit');button.disabled=!!a.errors.length;
 }
 App.actions['analyze-catalog']=async(_,button)=>{
  ensureManager();button.disabled=true;
  try{await analyze(App.data.catalogImport.source,currentMapping(),Number(document.getElementById('field-header_row').value),App.data.catalogImport.report);}
  catch(error){showError(error.message);}finally{button.disabled=false;}
 };
})();
