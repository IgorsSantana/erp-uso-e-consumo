-- Schema inicial para o ERP Uso e Consumo
-- Utilizando o banco de dados do TiDB Cloud

-- 1. Lojas (Filiais)
CREATE TABLE Lojas (
    ID INT PRIMARY KEY,
    Nome VARCHAR(50) NOT NULL
);

INSERT INTO Lojas (ID, Nome) VALUES 
(1, 'BCS'), (3, 'SJN'), (4, 'MEP'), (5, 'FCL1'), (6, 'FCL2'), (7, 'FCL3'), (8, 'FCL4');

-- 2. Seções
CREATE TABLE Secoes (
    ID INT AUTO_INCREMENT PRIMARY KEY,
    Nome VARCHAR(50) NOT NULL UNIQUE
);

INSERT INTO Secoes (Nome) VALUES 
('Embalagem'), ('Limpeza'), ('Consumo Geral'), ('Escritório'), 
('Açougue'), ('Bobina PDV'), ('Etiquetas'), ('Bobina Estrela');

-- 3. Produtos
CREATE TABLE Produtos (
    Codigo_ERP_Principal VARCHAR(20) PRIMARY KEY,
    Nome VARCHAR(100) NOT NULL,
    Destinacao_de_Uso VARCHAR(100),
    Referencia VARCHAR(50),
    Secao_ID INT,
    Periodo_Consumo VARCHAR(20) DEFAULT 'Mensal',
    Estoque_Atual DECIMAL(10,2) DEFAULT 0,
    Custo DECIMAL(10,2) NOT NULL,
    FOREIGN KEY (Secao_ID) REFERENCES Secoes(ID) ON DELETE SET NULL
);

-- 4. Controle de Estoque por Loja (Estoque Máximo e Mínimo específicos)
CREATE TABLE Estoque_Loja (
    Produto_ID VARCHAR(20),
    Loja_ID INT,
    Estoque_Minimo DECIMAL(10,2) DEFAULT 0,
    Estoque_Maximo DECIMAL(10,2) DEFAULT 0,
    PRIMARY KEY (Produto_ID, Loja_ID),
    FOREIGN KEY (Produto_ID) REFERENCES Produtos(Codigo_ERP_Principal) ON DELETE CASCADE,
    FOREIGN KEY (Loja_ID) REFERENCES Lojas(ID) ON DELETE CASCADE
);

-- 5. Pedidos (Cabeçalho do Pedido)
CREATE TABLE Pedidos (
    ID INT AUTO_INCREMENT PRIMARY KEY,
    Loja_ID INT NOT NULL,
    Data_Pedido DATETIME DEFAULT CURRENT_TIMESTAMP,
    Status VARCHAR(20) DEFAULT 'Pendente',
    Custo_Total DECIMAL(10,2) DEFAULT 0,
    FOREIGN KEY (Loja_ID) REFERENCES Lojas(ID)
);

-- 6. Itens do Pedido
CREATE TABLE Pedido_Itens (
    Pedido_ID INT,
    Produto_ID VARCHAR(20),
    Quantidade DECIMAL(10,2) NOT NULL,
    Custo_Unitario DECIMAL(10,2) NOT NULL,
    PRIMARY KEY (Pedido_ID, Produto_ID),
    FOREIGN KEY (Pedido_ID) REFERENCES Pedidos(ID) ON DELETE CASCADE,
    FOREIGN KEY (Produto_ID) REFERENCES Produtos(Codigo_ERP_Principal)
);

-- 7. Sistema de Autenticacao
CREATE TABLE IF NOT EXISTS Usuarios (
    ID INT AUTO_INCREMENT PRIMARY KEY,
    Nome VARCHAR(100) NOT NULL,
    Username VARCHAR(50) NOT NULL UNIQUE,
    SenhaHash VARCHAR(255) NOT NULL,
    Nivel_Acesso VARCHAR(20) DEFAULT 'Operacional',
    Data_Criacao DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Insert admin default if not exists (using IGNORE or standard approach)
-- Em ferramentas SQL simples, vamos fazer a query via app ou manually para o Admin.
INSERT IGNORE INTO Usuarios (Nome, Username, SenhaHash, Nivel_Acesso) VALUES 
('Administrador', 'admin', 'scrypt:32768:8:1$E6R8uT0B9pQzSvyh$1a2b3c...mock_hash_vai_ser_trocado', 'Admin');
