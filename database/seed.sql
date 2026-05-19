USE shop_management;

INSERT INTO categories(name)
VALUES
('Electronics'),
('Groceries'),
('Beverages');

INSERT INTO users(username, password_hash, role)
VALUES
(
    'admin',
    'PASTE_HASH_HERE',
    'admin'
);