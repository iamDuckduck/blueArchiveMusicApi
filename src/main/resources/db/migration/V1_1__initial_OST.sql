-- Create OST_type table
CREATE TABLE OST_type (
                          id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
                          volume INTEGER UNIQUE,
                          name VARCHAR(255) NOT NULL UNIQUE
);

-- Create OST table
CREATE TABLE OST (
                     id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
                     OST_number INTEGER,
                     name VARCHAR,
                     author VARCHAR,
                     image_path VARCHAR(255) NOT NULL,
                     audio_path VARCHAR(255) NOT NULL,
                     OST_type_id INTEGER NOT NULL,
                     FOREIGN KEY (OST_type_id) REFERENCES OST_type(id) ON DELETE CASCADE
);
