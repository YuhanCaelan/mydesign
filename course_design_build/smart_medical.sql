-- 慧医云课程设计版 MySQL 8.0 数据库脚本
-- 内容：建库、核心业务表、索引、外键及可直接登录的初始化测试数据。
SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;
DROP DATABASE IF EXISTS smart_medical;
CREATE DATABASE smart_medical DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE smart_medical;

CREATE TABLE sys_user (
  id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '用户主键',
  username VARCHAR(50) NOT NULL UNIQUE COMMENT '登录名',
  password_hash VARCHAR(255) NOT NULL COMMENT 'PBKDF2 密码散列',
  full_name VARCHAR(50) NOT NULL COMMENT '姓名',
  role VARCHAR(20) NOT NULL COMMENT 'admin/doctor/patient',
  phone VARCHAR(20), is_active TINYINT(1) NOT NULL DEFAULT 1,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_user_role(role)
) ENGINE=InnoDB COMMENT='系统用户';

CREATE TABLE department (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  name VARCHAR(80) NOT NULL UNIQUE COMMENT '科室名称',
  description VARCHAR(500) NOT NULL DEFAULT '',
  status VARCHAR(20) NOT NULL DEFAULT 'active',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_department_status(status)
) ENGINE=InnoDB COMMENT='医院科室';

CREATE TABLE doctor (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  user_id BIGINT NOT NULL UNIQUE, department_id BIGINT NOT NULL,
  doctor_no VARCHAR(20) NOT NULL UNIQUE, title VARCHAR(50) NOT NULL DEFAULT '医师',
  specialty VARCHAR(200) NOT NULL DEFAULT '', introduction TEXT,
  is_available TINYINT(1) NOT NULL DEFAULT 1,
  CONSTRAINT fk_doctor_user FOREIGN KEY(user_id) REFERENCES sys_user(id),
  CONSTRAINT fk_doctor_department FOREIGN KEY(department_id) REFERENCES department(id),
  INDEX idx_doctor_department(department_id)
) ENGINE=InnoDB COMMENT='医师档案';

CREATE TABLE patient (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  user_id BIGINT NOT NULL UNIQUE, patient_no VARCHAR(20) NOT NULL UNIQUE,
  gender VARCHAR(10) NOT NULL DEFAULT 'unknown', birth_date DATE,
  address VARCHAR(255) NOT NULL DEFAULT '', allergies TEXT,
  CONSTRAINT fk_patient_user FOREIGN KEY(user_id) REFERENCES sys_user(id)
) ENGINE=InnoDB COMMENT='患者档案';

CREATE TABLE doctor_schedule (
  id BIGINT PRIMARY KEY AUTO_INCREMENT, doctor_id BIGINT NOT NULL,
  schedule_date DATE NOT NULL, start_time TIME NOT NULL, end_time TIME NOT NULL,
  slot_minutes INT NOT NULL DEFAULT 30, is_active TINYINT(1) NOT NULL DEFAULT 1,
  CONSTRAINT fk_schedule_doctor FOREIGN KEY(doctor_id) REFERENCES doctor(id),
  CONSTRAINT uq_doctor_schedule UNIQUE(doctor_id,schedule_date,start_time,end_time),
  INDEX idx_schedule_date(schedule_date), INDEX idx_schedule_doctor(doctor_id)
) ENGINE=InnoDB COMMENT='医师排班';

CREATE TABLE appointment_slot (
  id BIGINT PRIMARY KEY AUTO_INCREMENT, schedule_id BIGINT NOT NULL,
  start_time TIME NOT NULL, end_time TIME NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'available' COMMENT 'available/booked/closed',
  CONSTRAINT fk_slot_schedule FOREIGN KEY(schedule_id) REFERENCES doctor_schedule(id) ON DELETE CASCADE,
  CONSTRAINT uq_schedule_slot UNIQUE(schedule_id,start_time,end_time),
  INDEX idx_slot_schedule(schedule_id), INDEX idx_slot_status(status)
) ENGINE=InnoDB COMMENT='预约号源';

CREATE TABLE appointment (
  id BIGINT PRIMARY KEY AUTO_INCREMENT, appointment_no VARCHAR(30) NOT NULL UNIQUE,
  patient_id BIGINT NOT NULL, doctor_id BIGINT NOT NULL, department_id BIGINT NOT NULL, slot_id BIGINT NOT NULL,
  reason VARCHAR(300) NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'pending' COMMENT 'pending/in_progress/completed/cancelled/no_show',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_appointment_patient FOREIGN KEY(patient_id) REFERENCES patient(id),
  CONSTRAINT fk_appointment_doctor FOREIGN KEY(doctor_id) REFERENCES doctor(id),
  CONSTRAINT fk_appointment_department FOREIGN KEY(department_id) REFERENCES department(id),
  CONSTRAINT fk_appointment_slot FOREIGN KEY(slot_id) REFERENCES appointment_slot(id),
  INDEX idx_appointment_patient(patient_id,status), INDEX idx_appointment_doctor(doctor_id,status),
  INDEX idx_appointment_created(created_at)
) ENGINE=InnoDB COMMENT='门诊预约';

CREATE TABLE medical_record (
  id BIGINT PRIMARY KEY AUTO_INCREMENT, appointment_id BIGINT NOT NULL UNIQUE,
  chief_complaint TEXT NOT NULL, diagnosis TEXT NOT NULL, treatment TEXT,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_record_appointment FOREIGN KEY(appointment_id) REFERENCES appointment(id)
) ENGINE=InnoDB COMMENT='门诊病历';

CREATE TABLE medicine (
  id BIGINT PRIMARY KEY AUTO_INCREMENT, name VARCHAR(100) NOT NULL,
  specification VARCHAR(100) NOT NULL DEFAULT '', unit VARCHAR(20) NOT NULL DEFAULT '盒',
  price DECIMAL(10,2) NOT NULL DEFAULT 0, stock INT NOT NULL DEFAULT 0,
  is_active TINYINT(1) NOT NULL DEFAULT 1,
  CONSTRAINT uq_medicine UNIQUE(name,specification)
) ENGINE=InnoDB COMMENT='药品目录';

-- 三类演示账号。对应密码写在部署说明中，数据库仅存散列。
INSERT INTO sys_user(id,username,password_hash,full_name,role,phone) VALUES
(1,'admin','pbkdf2_sha256$a1b2c3d4e5f60708$cef6effa17187bb6310a3160a664ad4fd5058a795702736c33838c24f61d4d5f','系统管理员','admin','13800000001'),
(2,'doctor','pbkdf2_sha256$b1c2d3e4f5060708$48b59456e7b87dd8adf43d0f3dc73455c2c7342d4bc0e8a677a508f011c772ef','张医生','doctor','13800000002'),
(3,'patient','pbkdf2_sha256$c1d2e3f405060708$0db5b1dc40713bfd12a69b06d0a78193620aec2eaa87dfc8c9f85ba68a1169d7','李患者','patient','13800000003'),
(4,'doctor2','pbkdf2_sha256$b1c2d3e4f5060708$48b59456e7b87dd8adf43d0f3dc73455c2c7342d4bc0e8a677a508f011c772ef','王医生','doctor','13800000004');

INSERT INTO department(id,name,description,status) VALUES
(1,'内科','负责常见内科疾病诊疗','active'),(2,'外科','负责外科疾病诊疗与术后随访','active'),
(3,'儿科','负责儿童常见疾病诊疗','active'),(4,'口腔科','负责口腔疾病诊疗','active');
INSERT INTO doctor(id,user_id,department_id,doctor_no,title,specialty,introduction) VALUES
(1,2,1,'D000001','主治医师','呼吸系统疾病','擅长呼吸系统常见病诊治'),
(2,4,2,'D000002','副主任医师','普通外科','擅长普通外科及术后管理');
INSERT INTO patient(id,user_id,patient_no,gender,birth_date,address,allergies) VALUES
(1,3,'P000001','male','2000-05-18','北京市海淀区','青霉素过敏');

-- 使用相对当前日期的排班，导入后可以立即演示预约。
INSERT INTO doctor_schedule(id,doctor_id,schedule_date,start_time,end_time,slot_minutes,is_active) VALUES
(1,1,DATE_ADD(CURDATE(),INTERVAL 1 DAY),'08:00:00','12:00:00',30,1),
(2,2,DATE_ADD(CURDATE(),INTERVAL 1 DAY),'14:00:00','17:00:00',30,1),
(3,1,DATE_ADD(CURDATE(),INTERVAL 2 DAY),'08:00:00','12:00:00',30,1);
INSERT INTO appointment_slot(schedule_id,start_time,end_time,status) VALUES
(1,'08:00:00','08:30:00','booked'),(1,'08:30:00','09:00:00','available'),(1,'09:00:00','09:30:00','available'),(1,'09:30:00','10:00:00','available'),
(1,'10:00:00','10:30:00','available'),(1,'10:30:00','11:00:00','available'),(1,'11:00:00','11:30:00','available'),(1,'11:30:00','12:00:00','available'),
(2,'14:00:00','14:30:00','available'),(2,'14:30:00','15:00:00','available'),(2,'15:00:00','15:30:00','available'),
(2,'15:30:00','16:00:00','available'),(2,'16:00:00','16:30:00','available'),(2,'16:30:00','17:00:00','available'),
(3,'08:00:00','08:30:00','available'),(3,'08:30:00','09:00:00','available'),(3,'09:00:00','09:30:00','available'),(3,'09:30:00','10:00:00','available');
INSERT INTO appointment(id,appointment_no,patient_id,doctor_id,department_id,slot_id,reason,status) VALUES
(1,'A202610220001',1,1,1,1,'咳嗽伴发热两天','pending');
INSERT INTO medicine(name,specification,unit,price,stock) VALUES
('阿莫西林胶囊','0.25g×24粒','盒',18.50,120),('布洛芬缓释胶囊','0.3g×20粒','盒',25.80,80),('氯雷他定片','10mg×12片','盒',16.00,60);
SET FOREIGN_KEY_CHECKS = 1;
