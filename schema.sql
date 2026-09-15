SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS technician_locations;
DROP TABLE IF EXISTS notifications;
DROP TABLE IF EXISTS status_history;
DROP TABLE IF EXISTS appointments;
DROP TABLE IF EXISTS service_requests;
DROP TABLE IF EXISTS service_types;
DROP TABLE IF EXISTS users;

CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    role ENUM('customer', 'technician') NOT NULL,
    phone VARCHAR(30),
    address TEXT,
    latitude DECIMAL(10,7), longitude DECIMAL(10,7),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    available BOOLEAN NOT NULL DEFAULT TRUE,
    sharing_location BOOLEAN NOT NULL DEFAULT FALSE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE service_types (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    estimated_minutes INT NOT NULL DEFAULT 60
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE service_requests (
    id INT AUTO_INCREMENT PRIMARY KEY,
    customer_id INT NOT NULL, service_type_id INT NOT NULL,
    description TEXT,
    status ENUM('Pending','Scheduled','In Progress','Completed','Cancelled','Rescheduled') NOT NULL DEFAULT 'Pending',
    preferred_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (customer_id) REFERENCES users(id),
    FOREIGN KEY (service_type_id) REFERENCES service_types(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE appointments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    request_id INT NOT NULL, technician_id INT NOT NULL,
    start_time DATETIME NOT NULL, end_time DATETIME NOT NULL, notes TEXT,
    FOREIGN KEY (request_id) REFERENCES service_requests(id) ON DELETE CASCADE,
    FOREIGN KEY (technician_id) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE status_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    request_id INT NOT NULL, status VARCHAR(30) NOT NULL,
    note TEXT, changed_by INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (request_id) REFERENCES service_requests(id) ON DELETE CASCADE,
    FOREIGN KEY (changed_by) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE notifications (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL, message VARCHAR(255) NOT NULL,
    link VARCHAR(255), is_read BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE technician_locations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    technician_id INT NOT NULL,
    latitude DECIMAL(10,7) NOT NULL, longitude DECIMAL(10,7) NOT NULL,
    accuracy DECIMAL(8,2), recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (technician_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX latest_location (technician_id, recorded_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
SET FOREIGN_KEY_CHECKS = 1;
