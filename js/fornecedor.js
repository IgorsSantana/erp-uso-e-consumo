(() => {
  'use strict';

  const token = new URLSearchParams(window.location.search).get('token');
  const money = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });
  const number = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 3 });
  const state = { items: [], fields: [], data: null, open: false, dirty: false, saving: false };
  const $ = (id) => document.getElementById(id);
  const endpoint = token ? `/api/portal-fornecedor/${encodeURIComponent(token)}` : '';

  function element(tag, className, content) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (content !== undefined && content !== null) node.textContent = String(content);
    return node;
  }

  function parsePrice(value) {
    let raw = String(value ?? '').trim().replace(/\s/g, '');
    if (!raw) return null;
    if (raw.includes(',')) {
      if (!/^(?:\d+|\d{1,3}(?:\.\d{3})+),\d{1,4}$/.test(raw) && !/^\d+,$/.test(raw)) return NaN;
      raw = raw.replace(/\./g, '').replace(',', '.');
    } else if (!/^\d+(?:\.\d{1,4})?$/.test(raw)) return NaN;
    const result = Number(raw);
    return Number.isFinite(result) && result >= 0 && result <= 1000000000 ? result : NaN;
  }

  function quantity(item) {
    const value = Number(item.qtd ?? item.quantidade ?? 1);
    return Number.isFinite(value) && value > 0 ? value : 1;
  }

  function formatDate(value) {
    if (!value) return 'Sem prazo definido';
    const raw = String(value);
    const dateOnly = /^(\d{4})-(\d{2})-(\d{2})/.exec(raw);
    if (dateOnly) return `${dateOnly[3]}/${dateOnly[2]}/${dateOnly[1]}`;
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? raw : parsed.toLocaleDateString('pt-BR');
  }

  function deadlinePassed(value) {
    if (!value) return false;
    const raw = String(value).slice(0, 10);
    if (!/^\d{4}-\d{2}-\d{2}$/.test(raw)) return false;
    const today = new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Sao_Paulo', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());
    return raw < today;
  }

  async function request(options = {}) {
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), 25000);
    try {
      const response = await fetch(endpoint, { ...options, signal: controller.signal, credentials: 'omit', cache: 'no-store', headers: { Accept: 'application/json', ...(options.headers || {}) } });
      let data;
      try { data = await response.json(); } catch (_) { throw new Error('O servidor não retornou uma resposta válida. Tente novamente em instantes.'); }
      if (!response.ok) {
        const error = new Error(data.error || data.message || 'Não foi possível concluir a solicitação. Tente novamente.');
        error.status = response.status;
        throw error;
      }
      return data;
    } catch (error) {
      if (error.name === 'AbortError') throw new Error('O servidor demorou para responder. Verifique sua conexão e tente novamente.');
      if (error instanceof TypeError) throw new Error('Não foi possível conectar ao servidor. Verifique sua conexão e tente novamente.');
      throw error;
    } finally {
      window.clearTimeout(timer);
    }
  }

  function showLoadingError(message, retry) {
    $('loading').hidden = true;
    $('error-message').textContent = message;
    $('btn-retry').hidden = !retry;
    $('error-box').hidden = false;
    $('error-box').focus();
  }

  function field(label, id, help) {
    const wrapper = element('div', 'field');
    const labelNode = element('label', '', label);
    labelNode.htmlFor = id;
    wrapper.append(labelNode);
    if (help) {
      const hint = element('span', 'field-help', help);
      hint.id = `${id}-help`;
      wrapper.append(hint);
    }
    return wrapper;
  }

  function buildItem(item, index, savedPrice, details) {
    const card = element('article', 'item-card');
    const heading = element('div', 'item-heading');
    const itemName = element('div', 'item-name');
    const title = element('h3', '', item.nome || `Material ${index + 1}`);
    title.id = `item-title-${index}`;
    itemName.append(title, element('p', 'item-ref', `Código: ${item.id}`));
    card.setAttribute('aria-labelledby', title.id);
    heading.append(element('span', 'item-number', String(index + 1).padStart(2, '0')), itemName, element('span', 'quantity', `${number.format(quantity(item))} ${item.unidade || 'un.'}`));
    card.append(heading);

    const grid = element('div', 'item-fields');
    const priceId = `price-${index}`;
    const priceField = field('Preço unitário', priceId);
    const priceWrap = element('div', 'price-wrap');
    const price = element('input');
    price.type = 'text';
    price.inputMode = 'decimal';
    price.id = priceId;
    price.name = priceId;
    price.placeholder = '0,00';
    price.autocomplete = 'off';
    price.maxLength = 22;
    price.setAttribute('aria-label', `Preço unitário de ${item.nome || 'material'}, em reais`);
    if (savedPrice !== undefined && savedPrice !== null && Number(savedPrice) > 0) price.value = Number(savedPrice).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 4 });
    priceWrap.append(element('span', '', 'R$'), price);
    const precisionHint = element('span', 'field-help', 'Até 4 casas decimais.');
    precisionHint.id = `${priceId}-precision`;
    price.setAttribute('aria-describedby', precisionHint.id);
    priceField.append(priceWrap, precisionHint);

    const deliveryId = `delivery-${index}`;
    const deliveryField = field('Entrega em dias corridos', deliveryId);
    const delivery = element('input');
    delivery.type = 'number';
    delivery.id = deliveryId;
    delivery.name = deliveryId;
    delivery.min = '0';
    delivery.max = '3650';
    delivery.step = '1';
    delivery.inputMode = 'numeric';
    delivery.placeholder = 'Opcional';
    delivery.setAttribute('aria-label', `Prazo de entrega de ${item.nome || 'material'}, em dias corridos`);
    if (details.prazo_entrega !== undefined && details.prazo_entrega !== null && details.prazo_entrega !== '') delivery.value = details.prazo_entrega;
    deliveryField.append(delivery);
    grid.append(priceField, deliveryField);
    card.append(grid);

    const toggle = element('button', 'details-toggle', details.observacoes ? 'Ocultar observação' : 'Adicionar observação ao item');
    toggle.type = 'button';
    toggle.setAttribute('aria-expanded', details.observacoes ? 'true' : 'false');
    const notesId = `notes-${index}`;
    const detailsBox = element('div', 'item-details');
    detailsBox.id = `details-${index}`;
    detailsBox.hidden = !details.observacoes;
    toggle.setAttribute('aria-controls', detailsBox.id);
    const notesField = field('Observação do item (opcional)', notesId);
    const notes = element('textarea');
    notes.id = notesId;
    notes.name = notesId;
    notes.rows = 2;
    notes.maxLength = 500;
    notes.placeholder = 'Marca ofertada, embalagem ou outra informação relevante.';
    notes.value = details.observacoes || '';
    notesField.append(notes);
    detailsBox.append(notesField);
    toggle.addEventListener('click', () => {
      detailsBox.hidden = !detailsBox.hidden;
      toggle.setAttribute('aria-expanded', String(!detailsBox.hidden));
      toggle.textContent = detailsBox.hidden ? 'Adicionar observação ao item' : 'Ocultar observação';
      if (!detailsBox.hidden) notes.focus();
    });
    card.append(toggle, detailsBox);

    const bottom = element('div', 'item-bottom');
    const unavailableLabel = element('label', 'unavailable');
    const unavailable = element('input');
    unavailable.type = 'checkbox';
    unavailable.id = `unavailable-${index}`;
    unavailable.checked = Boolean(details.indisponivel);
    unavailableLabel.append(unavailable, document.createTextNode('Não forneço este item'));
    const totalNode = element('strong', '', money.format(0));
    const total = element('div', 'item-total', 'Subtotal');
    total.append(totalNode);
    bottom.append(unavailableLabel, total);
    card.append(bottom);
    const record = { item, card, price, delivery, notes, unavailable, total: totalNode };

    const update = () => {
      state.dirty = true;
      $('form-error').hidden = true;
      price.removeAttribute('aria-invalid');
      delivery.removeAttribute('aria-invalid');
      refreshItem(record);
      updateSummary();
    };
    price.addEventListener('input', update);
    price.addEventListener('blur', () => {
      const value = parsePrice(price.value);
      if (value !== null && Number.isFinite(value)) price.value = value.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 4 });
    });
    delivery.addEventListener('input', update);
    notes.addEventListener('input', update);
    unavailable.addEventListener('change', update);
    state.fields.push(record);
    refreshItem(record);
    return card;
  }

  function refreshItem(record) {
    const unavailable = record.unavailable.checked;
    record.card.classList.toggle('is-unavailable', unavailable);
    record.price.disabled = !state.open || unavailable;
    record.delivery.disabled = !state.open || unavailable;
    record.notes.disabled = !state.open;
    record.unavailable.disabled = !state.open;
    const price = parsePrice(record.price.value);
    record.total.textContent = unavailable ? 'Indisponível' : money.format(Number.isFinite(price) ? price * quantity(record.item) : 0);
  }

  function summary() {
    let total = 0;
    let priced = 0;
    let unavailable = 0;
    state.fields.forEach((record) => {
      if (record.unavailable.checked) { unavailable += 1; return; }
      const price = parsePrice(record.price.value);
      if (Number.isFinite(price) && price > 0) { priced += 1; total += price * quantity(record.item); }
    });
    return { total, priced, unavailable };
  }

  function updateSummary() {
    const values = summary();
    $('summary-items').textContent = state.items.length;
    $('summary-priced').textContent = values.priced;
    $('summary-unavailable').textContent = values.unavailable;
    $('total-cotacao').textContent = money.format(values.total);
  }

  function render(data) {
    state.data = data;
    state.items = Array.isArray(data.itens) ? data.itens : [];
    state.fields = [];
    const quote = data.cotacao || {};
    const status = String(quote.Status || '').toLocaleLowerCase('pt-BR');
    state.open = ['aberta', 'aberto', 'open'].includes(status) && data.pode_responder !== false && !deadlinePassed(quote.Data_Limite);
    $('view-titulo').textContent = quote.Titulo || 'Cotação de materiais';
    $('view-fornecedor-nome').textContent = data.fornecedor_nome || 'Fornecedor convidado';
    $('view-status').textContent = state.open ? 'Cotação aberta' : 'Cotação encerrada';
    $('view-status').classList.toggle('closed', !state.open);
    $('view-deadline').textContent = formatDate(quote.Data_Limite);
    $('view-item-count').textContent = `${state.items.length} ${state.items.length === 1 ? 'item' : 'itens'}`;
    $('view-observacoes').textContent = quote.Observacoes || '';
    $('view-observacoes').hidden = !quote.Observacoes;
    $('alert-preencheu-aviso').hidden = !data.preencheu || !state.open;
    $('closed-notice').hidden = state.open;
    $('proposal-notes').value = data.observacoes || data.observacoes_proposta || '';
    $('proposal-notes').disabled = !state.open;
    const container = $('lista-itens');
    container.replaceChildren();
    state.items.forEach((item, index) => {
      const saved = (data.respostas || {})[item.id];
      const details = (data.respostas_detalhes || {})[item.id] || (saved && typeof saved === 'object' ? saved : {});
      const price = saved && typeof saved === 'object' ? saved.preco ?? saved.Preco_Unitario : saved;
      container.append(buildItem(item, index, price, details));
    });
    if (!state.items.length) container.append(element('div', 'panel empty-state', 'Esta cotação ainda não possui itens. Entre em contato com a equipe de compras.'));
    $('btn-enviar').hidden = !state.open || !state.items.length;
    $('btn-print').hidden = state.open;
    $('submit-label').textContent = data.preencheu ? 'Atualizar proposta' : 'Enviar proposta';
    updateSummary();
    state.dirty = false;
    $('loading').hidden = true;
    $('error-box').hidden = true;
    $('success-box').hidden = true;
    $('cotacao-content').hidden = false;
  }

  async function load() {
    if (!token || token.length > 512) {
      showLoadingError('Este portal é acessado por um convite pessoal. Abra o link completo enviado pela equipe de compras.', false);
      return;
    }
    $('loading').hidden = false;
    $('error-box').hidden = true;
    try {
      const data = await request();
      if (!data || !data.cotacao || !Array.isArray(data.itens)) throw new Error('Os dados desta cotação estão incompletos. Solicite um novo convite à equipe de compras.');
      render(data);
    } catch (error) {
      showLoadingError(error.message, ![400, 403, 404, 410].includes(error.status));
    }
  }

  function formError(message, control) {
    $('form-error').textContent = message;
    $('form-error').hidden = false;
    if (control) {
      control.setAttribute('aria-invalid', 'true');
      control.focus();
      control.scrollIntoView({ block: 'center', behavior: 'smooth' });
    } else $('form-error').focus();
  }

  async function submit(event) {
    event.preventDefault();
    if (!state.open || state.saving) return;
    $('form-error').hidden = true;
    const respostas = [];
    for (const record of state.fields) {
      const unavailable = record.unavailable.checked;
      const price = parsePrice(record.price.value);
      if (!unavailable && (!Number.isFinite(price) || price <= 0)) {
        formError(`Informe um preço unitário maior que zero para “${record.item.nome}” ou marque que não fornece este item. Use até quatro casas decimais.`, record.price);
        return;
      }
      const delivery = record.delivery.value.trim();
      if (!unavailable && delivery !== '' && (!/^\d+$/.test(delivery) || Number(delivery) > 3650)) {
        formError('O prazo de entrega deve ser um número inteiro entre 0 e 3.650 dias.', record.delivery);
        return;
      }
      respostas.push({ produto_id: record.item.id, preco: unavailable ? 0 : price, prazo_entrega: unavailable || delivery === '' ? null : Number(delivery), observacoes: record.notes.value.trim(), indisponivel: unavailable });
    }
    if (!respostas.length) { formError('Esta cotação não possui itens para responder. Entre em contato com a equipe de compras.'); return; }
    state.saving = true;
    const disabledControls = Array.from($('proposal-form').elements, (control) => [control, control.disabled]);
    disabledControls.forEach(([control]) => { control.disabled = true; });
    $('submit-label').textContent = 'Enviando proposta…';
    $('proposal-form').setAttribute('aria-busy', 'true');
    try {
      const observacoes = $('proposal-notes').value.trim();
      await request({ method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ respostas, observacoes }) });
      state.dirty = false;
      state.data.preencheu = true;
      state.data.observacoes = observacoes;
      state.data.respostas = {};
      state.data.respostas_detalhes = {};
      respostas.forEach((response) => {
        state.data.respostas[response.produto_id] = response.preco;
        state.data.respostas_detalhes[response.produto_id] = { prazo_entrega: response.prazo_entrega, observacoes: response.observacoes, indisponivel: response.indisponivel };
      });
      const values = summary();
      $('success-total').textContent = money.format(values.total);
      $('success-detail').textContent = `${values.priced} ${values.priced === 1 ? 'item cotado' : 'itens cotados'} · ${values.unavailable} ${values.unavailable === 1 ? 'indisponível' : 'indisponíveis'} · Enviada em ${new Date().toLocaleString('pt-BR', { timeZone: 'America/Sao_Paulo' })}`;
      $('success-message').textContent = `Obrigado, ${state.data.fornecedor_nome || 'fornecedor'}! Sua proposta já está disponível para nossa equipe de compras.`;
      $('cotacao-content').hidden = true;
      $('success-box').hidden = false;
      $('success-box').focus();
      window.scrollTo({ top: 0, behavior: 'smooth' });
    } catch (error) {
      formError(error.message);
    } finally {
      state.saving = false;
      disabledControls.forEach(([control, disabled]) => { control.disabled = disabled; });
      $('submit-label').textContent = state.data.preencheu ? 'Atualizar proposta' : 'Enviar proposta';
      $('proposal-form').removeAttribute('aria-busy');
    }
  }

  function printProposal() {
    const wasHidden = $('cotacao-content').hidden;
    $('cotacao-content').hidden = false;
    window.print();
    $('cotacao-content').hidden = wasHidden;
  }

  $('btn-retry').addEventListener('click', load);
  $('proposal-form').addEventListener('submit', submit);
  $('proposal-notes').addEventListener('input', () => { state.dirty = true; });
  $('btn-edit').addEventListener('click', () => {
    render(state.data);
    $('view-titulo').scrollIntoView({ block: 'start', behavior: 'smooth' });
  });
  $('btn-print').addEventListener('click', printProposal);
  $('btn-print-success').addEventListener('click', printProposal);
  window.addEventListener('beforeunload', (event) => {
    if (!state.dirty) return;
    event.preventDefault();
    event.returnValue = '';
  });
  load();
})();
