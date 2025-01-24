--CREATE DATABASE ddl
--USE ddl

-- Create table Medicine

CREATE TABLE Medicine (
    MedicineID INT PRIMARY KEY,
    MedicineName VARCHAR(50) NOT NULL,
    Manufacturer VARCHAR(50) NOT NULL,
    StockQuantity INT DEFAULT 0 CHECK (StockQuantity >= 0),
    Price DECIMAL(10, 2) CHECK (Price >= 0)
);
GO

-- Create table Department
CREATE TABLE Department (
    DepartmentID INT PRIMARY KEY,
    DepartmentName VARCHAR(100) NOT NULL,
    Location VARCHAR(100),
    PhoneExtension VARCHAR(5)
);
GO

-- Create table Staff
CREATE TABLE Staff (
    StaffID INT PRIMARY KEY,
    FirstName VARCHAR(100) NOT NULL,
    LastName VARCHAR(100) NOT NULL,
    Role VARCHAR(100),
    DepartmentID INT,
    PhoneNumber VARCHAR(15) UNIQUE NOT NULL,
    Email VARCHAR(255) UNIQUE NOT NULL,
    ShiftHours VARCHAR(100),
    FOREIGN KEY (DepartmentID) REFERENCES Department(DepartmentID) ON DELETE CASCADE ON UPDATE CASCADE
);
GO

-- Create Medical_Record table
CREATE TABLE Medical_Record (
    RecordID INT PRIMARY KEY,
    PatientID INT NOT NULL,
    DoctorID INT NOT NULL,
    VisitDate DATE,
    Diagnosis TEXT,
    TreatmentPlan TEXT,
    Prescription TEXT,
    FOREIGN KEY (PatientID) REFERENCES Patient(PatientID) ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (DoctorID) REFERENCES Doctor(DoctorID) ON DELETE CASCADE ON UPDATE CASCADE
);
GO

-- Create table Room
CREATE TABLE Room (
    RoomID INT PRIMARY KEY,
    RoomNumber VARCHAR(10) UNIQUE NOT NULL,
    DepartmentID INT,
    RoomType VARCHAR(10) NOT NULL CHECK (RoomType IN ('General', 'Private', 'ICU')),
    AvailabilityStatus VARCHAR(10) NOT NULL DEFAULT 'Available' CHECK (AvailabilityStatus IN ('Available', 'Occupied')),
    FOREIGN KEY (DepartmentID) REFERENCES Department(DepartmentID) ON DELETE CASCADE ON UPDATE CASCADE
);
GO

-- Create table Doctor
CREATE TABLE Doctor (
    DoctorID INT PRIMARY KEY,
    FirstName VARCHAR(100) NOT NULL,
    LastName VARCHAR(100) NOT NULL,
    Specialization VARCHAR(100),
    PhoneNumber VARCHAR(15) UNIQUE NOT NULL,
    Email VARCHAR(255) UNIQUE NOT NULL,
    DepartmentID INT,
    Availability BIT DEFAULT 1,
    FOREIGN KEY (DepartmentID) REFERENCES Department(DepartmentID) ON DELETE CASCADE ON UPDATE CASCADE
);
GO

-- Create Patient table 
CREATE TABLE Patient (
    PatientID INT PRIMARY KEY,
    FirstName VARCHAR(100) NOT NULL,
    LastName VARCHAR(100) NOT NULL,
    DateOfBirth DATE,
    Gender VARCHAR(15) CHECK (Gender IN ('Male', 'Female')),
    Address VARCHAR(100),
    PhoneNumber VARCHAR(15) UNIQUE NOT NULL,
    Email VARCHAR(255) UNIQUE NOT NULL,
	EmergencyContactName VARCHAR(200),
	EmergencyContactPhone VARCHAR(15)
);
GO

-- Create Billing table
CREATE TABLE Billing (
    BillingID INT PRIMARY KEY,
    PatientID INT NOT NULL,
    TotalAmount DECIMAL(12, 2),
    PaymentStatus VARCHAR(10) CHECK (PaymentStatus IN ('Paid', 'Unpaid')),
    PaymentDate DATE,
    PaymentMethod VARCHAR(50),
    FOREIGN KEY (PatientID) REFERENCES Patient(PatientID) ON DELETE CASCADE ON UPDATE CASCADE
);
GO

-- Create table Prescription
CREATE TABLE Prescription (
    PrescriptionID INT PRIMARY KEY,
    RecordID INT NOT NULL,
    MedicineID INT NOT NULL,
    Dosage VARCHAR(50),
    Frequency VARCHAR(50),
    Duration VARCHAR(50),
    FOREIGN KEY (RecordID) REFERENCES Medical_Record(RecordID) ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (MedicineID) REFERENCES Medicine(MedicineID) ON DELETE CASCADE ON UPDATE CASCADE
);
GO

-- Create table Room_Assignment
CREATE TABLE Room_Assignment (
    AssignmentID INT PRIMARY KEY,
    RoomID INT NOT NULL,
    PatientID INT NOT NULL,
    AdmissionDate DATE,
    DischargeDate DATE NULL,
	CHECK (DischargeDate IS NULL OR DischargeDate >= AdmissionDate),
    FOREIGN KEY (RoomID) REFERENCES Room(RoomID) ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (PatientID) REFERENCES Patient(PatientID) ON DELETE CASCADE ON UPDATE CASCADE
);
GO

-- Create table Appointment
CREATE TABLE Appointment (
    AppointmentID INT PRIMARY KEY,
    PatientID INT NOT NULL,
    DoctorID INT NOT NULL,
    DepartmentID INT,
    AppointmentDate DATE,
    AppointmentTime TIME,
    Status VARCHAR(15) NOT NULL DEFAULT 'Scheduled' CHECK (Status IN ('Scheduled', 'Completed', 'Cancelled')),
    FOREIGN KEY (PatientID) REFERENCES Patient(PatientID) ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (DoctorID) REFERENCES Doctor(DoctorID) ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (DepartmentID) REFERENCES Department(DepartmentID) ON DELETE NO ACTION ON UPDATE NO ACTION
);
GO