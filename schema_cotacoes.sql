-- Nova Extensão do Schema ERP: Portal de Cotações

-- 7. Fornecedores
CREATE TABLE IF NOT EXISTS Fornecedores (
    ID INT AUTO_INCREMENT PRIMARY KEY,
    Nome_Fantasia VARCHAR(100) NOT NULL,
    CNPJ VARCHAR(20),
    Contato_Nome VARCHAR(50),
    Email VARCHAR(100),
    Telefone VARCHAR(20),
    Ativo BOOLEAN DEFAULT TRUE,
    Criado_Em DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 8. Cotações (Cabeçalho da Campanha)
CREATE TABLE IF NOT EXISTS Cotacoes (
    ID INT AUTO_INCREMENT PRIMARY KEY,
    Titulo VARCHAR(100) NOT NULL,
    Data_Abertura DATETIME DEFAULT CURRENT_TIMESTAMP,
    Data_Encerramento DATETIME,
    Status VARCHAR(20) DEFAULT 'Aberta', -- Aberta, Encerrada, Cancelada
    Observacoes TEXT
);

-- 9. Itens Solicitados na Cotação
CREATE TABLE IF NOT EXISTS Cotacao_Itens (
    Cotacao_ID INT,
    Produto_ID VARCHAR(20),
    Quantidade_Solicitada DECIMAL(10,2) NOT NULL DEFAULT 1.0,
    PRIMARY KEY (Cotacao_ID, Produto_ID),
    FOREIGN KEY (Cotacao_ID) REFERENCES Cotacoes(ID) ON DELETE CASCADE,
    FOREIGN KEY (Produto_ID) REFERENCES Produtos(Codigo_ERP_Principal)
);

-- 10. Fornecedores Convidados para a Cotação (Gera o Token/Link Mágico)
CREATE TABLE IF NOT EXISTS Cotacao_Fornecedores (
    Cotacao_ID INT,
    Fornecedor_ID INT,
    Token_Acesso VARCHAR(64) UNIQUE NOT NULL, -- UUID ou Hash seguro
    Data_Envio DATETIME DEFAULT CURRENT_TIMESTAMP,
    Visualizou BOOLEAN DEFAULT FALSE,
    Data_Visualizacao DATETIME NULL,
    Preencheu BOOLEAN DEFAULT FALSE,
    Data_Preenchimento DATETIME NULL,
    PRIMARY KEY (Cotacao_ID, Fornecedor_ID),
    FOREIGN KEY (Cotacao_ID) REFERENCES Cotacoes(ID) ON DELETE CASCADE,
    FOREIGN KEY (Fornecedor_ID) REFERENCES Fornecedores(ID) ON DELETE CASCADE
);

-- 11. Respostas Digitadas pelos Fornecedores (Tabela de Lances)
CREATE TABLE IF NOT EXISTS Respostas_Cotacao (
    Cotacao_ID INT,
    Fornecedor_ID INT,
    Produto_ID VARCHAR(20),
    Preco_Unitario DECIMAL(10,4) NOT NULL, -- Até 4 casas para precisão de centavos em itens pequenos
    Observacao VARCHAR(255),
    Data_Resposta DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    Inativo_Para_Item BOOLEAN DEFAULT FALSE, -- Se o fornecedor disser "Não tenho esse item"
    Eh_Vencedor BOOLEAN DEFAULT FALSE, -- Flag calculada quando a cotação é encerrada
    PRIMARY KEY (Cotacao_ID, Fornecedor_ID, Produto_ID),
    FOREIGN KEY (Cotacao_ID, Fornecedor_ID) REFERENCES Cotacao_Fornecedores(Cotacao_ID, Fornecedor_ID) ON DELETE CASCADE,
    FOREIGN KEY (Produto_ID) REFERENCES Produtos(Codigo_ERP_Principal) ON DELETE CASCADE
);
