/* SQL Server 2022+; run in an empty user database (SSMS or sqlcmd -b).
   Bootstrap only: never drops tables or changes an existing database in place.
   Explicit IDs keep the original seed format. All deletes/updates are restricted
   when referenced: deactivate people instead of erasing clinical/financial history.
   Existing inserts.sql needs correction before use: see sql/README.md.
*/
SET NOCOUNT ON;
SET XACT_ABORT ON;
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
SET ANSI_PADDING ON;
SET ANSI_WARNINGS ON;
SET ARITHABORT ON;
SET CONCAT_NULL_YIELDS_NULL ON;
SET NUMERIC_ROUNDABORT OFF;

IF DB_NAME() IN (N'master', N'model', N'msdb', N'tempdb')
    THROW 50001, 'Select an empty user database before creating the hospital schema.', 1;

IF EXISTS (
    SELECT 1 FROM sys.tables
    WHERE schema_id = SCHEMA_ID(N'dbo') AND name IN (
        N'Department', N'Medicine', N'Patient', N'Staff', N'Doctor', N'Room',
        N'Appointment', N'Medical_Record', N'Prescription', N'Billing', N'Room_Assignment'
    )
)
    THROW 50002, 'Hospital tables already exist. Use a separate database or an explicit migration; nothing was dropped.', 1;

BEGIN TRY
    BEGIN TRANSACTION;

    -- Independent reference tables come before their dependants.
    CREATE TABLE dbo.Department (
        DepartmentID INT NOT NULL CONSTRAINT PK_Department PRIMARY KEY,
        DepartmentName NVARCHAR(100) NOT NULL,
        Location NVARCHAR(100) NULL,
        PhoneExtension VARCHAR(5) NULL,
        IsActive BIT NOT NULL CONSTRAINT DF_Department_IsActive DEFAULT (1),
        CONSTRAINT UQ_Department_Name UNIQUE (DepartmentName),
        CONSTRAINT CK_Department_Name CHECK (LEN(LTRIM(RTRIM(DepartmentName))) > 0)
    );

    CREATE TABLE dbo.Medicine (
        MedicineID INT NOT NULL CONSTRAINT PK_Medicine PRIMARY KEY,
        MedicineName NVARCHAR(100) NOT NULL,
        Manufacturer NVARCHAR(100) NOT NULL,
        StockQuantity INT NOT NULL CONSTRAINT DF_Medicine_Stock DEFAULT (0),
        Price DECIMAL(10, 2) NOT NULL,
        CONSTRAINT CK_Medicine_Stock CHECK (StockQuantity >= 0),
        CONSTRAINT CK_Medicine_Price CHECK (Price >= 0),
        CONSTRAINT CK_Medicine_Name CHECK (LEN(LTRIM(RTRIM(MedicineName))) > 0),
        CONSTRAINT CK_Medicine_Manufacturer CHECK (LEN(LTRIM(RTRIM(Manufacturer))) > 0)
    );

    CREATE TABLE dbo.Patient (
        PatientID INT NOT NULL CONSTRAINT PK_Patient PRIMARY KEY,
        FirstName NVARCHAR(100) NOT NULL,
        LastName NVARCHAR(100) NOT NULL,
        DateOfBirth DATE NOT NULL,
        Gender NVARCHAR(30) NULL,
        Address NVARCHAR(255) NULL,
        -- Contacts are optional and not unique: families can share them.
        PhoneNumber VARCHAR(30) NULL,
        Email NVARCHAR(254) NULL,
        EmergencyContactName NVARCHAR(200) NULL,
        EmergencyContactPhone VARCHAR(30) NULL,
        IsActive BIT NOT NULL CONSTRAINT DF_Patient_IsActive DEFAULT (1),
        CONSTRAINT CK_Patient_Name CHECK (
            LEN(LTRIM(RTRIM(FirstName))) > 0 AND LEN(LTRIM(RTRIM(LastName))) > 0
        )
    );

    CREATE TABLE dbo.Staff (
        StaffID INT NOT NULL CONSTRAINT PK_Staff PRIMARY KEY,
        FirstName NVARCHAR(100) NOT NULL,
        LastName NVARCHAR(100) NOT NULL,
        Role NVARCHAR(100) NOT NULL,
        DepartmentID INT NOT NULL,
        PhoneNumber VARCHAR(30) NULL,
        Email NVARCHAR(254) NULL,
        ShiftHours NVARCHAR(100) NULL, -- display label, not a scheduling calendar
        IsActive BIT NOT NULL CONSTRAINT DF_Staff_IsActive DEFAULT (1),
        CONSTRAINT FK_Staff_Department FOREIGN KEY (DepartmentID)
            REFERENCES dbo.Department (DepartmentID),
        CONSTRAINT CK_Staff_Name CHECK (
            LEN(LTRIM(RTRIM(FirstName))) > 0 AND LEN(LTRIM(RTRIM(LastName))) > 0
        ),
        CONSTRAINT CK_Staff_Role CHECK (LEN(LTRIM(RTRIM(Role))) > 0)
    );

    CREATE TABLE dbo.Doctor (
        DoctorID INT NOT NULL CONSTRAINT PK_Doctor PRIMARY KEY,
        FirstName NVARCHAR(100) NOT NULL,
        LastName NVARCHAR(100) NOT NULL,
        Specialization NVARCHAR(100) NOT NULL,
        PhoneNumber VARCHAR(30) NULL,
        Email NVARCHAR(254) NULL,
        DepartmentID INT NOT NULL, -- current home department, not historical attribution
        Availability BIT NOT NULL CONSTRAINT DF_Doctor_Availability DEFAULT (1),
        IsActive BIT NOT NULL CONSTRAINT DF_Doctor_IsActive DEFAULT (1),
        CONSTRAINT FK_Doctor_Department FOREIGN KEY (DepartmentID)
            REFERENCES dbo.Department (DepartmentID),
        CONSTRAINT CK_Doctor_Name CHECK (
            LEN(LTRIM(RTRIM(FirstName))) > 0 AND LEN(LTRIM(RTRIM(LastName))) > 0
        ),
        CONSTRAINT CK_Doctor_Specialization CHECK (LEN(LTRIM(RTRIM(Specialization))) > 0)
    );

    CREATE TABLE dbo.Room (
        RoomID INT NOT NULL CONSTRAINT PK_Room PRIMARY KEY,
        RoomNumber VARCHAR(10) NOT NULL CONSTRAINT UQ_Room_Number UNIQUE,
        DepartmentID INT NOT NULL,
        RoomType VARCHAR(10) NOT NULL,
        -- Legacy dashboard snapshot; assignments are needed to validate occupancy.
        AvailabilityStatus VARCHAR(10) NOT NULL CONSTRAINT DF_Room_Status DEFAULT ('Available'),
        CONSTRAINT FK_Room_Department FOREIGN KEY (DepartmentID)
            REFERENCES dbo.Department (DepartmentID),
        CONSTRAINT CK_Room_Number CHECK (LEN(LTRIM(RTRIM(RoomNumber))) > 0),
        CONSTRAINT CK_Room_Type CHECK (RoomType IN ('General', 'Private', 'ICU')),
        CONSTRAINT CK_Room_Status CHECK (AvailabilityStatus IN ('Available', 'Occupied'))
    );

    CREATE TABLE dbo.Appointment (
        AppointmentID INT NOT NULL CONSTRAINT PK_Appointment PRIMARY KEY,
        PatientID INT NOT NULL,
        DoctorID INT NOT NULL,
        DepartmentID INT NOT NULL, -- department of this appointment, retained historically
        AppointmentDate DATE NOT NULL,
        AppointmentTime TIME(0) NOT NULL,
        Status VARCHAR(15) NOT NULL CONSTRAINT DF_Appointment_Status DEFAULT ('Scheduled'),
        CONSTRAINT FK_Appointment_Patient FOREIGN KEY (PatientID) REFERENCES dbo.Patient (PatientID),
        CONSTRAINT FK_Appointment_Doctor FOREIGN KEY (DoctorID) REFERENCES dbo.Doctor (DoctorID),
        CONSTRAINT FK_Appointment_Department FOREIGN KEY (DepartmentID) REFERENCES dbo.Department (DepartmentID),
        CONSTRAINT CK_Appointment_Status CHECK (Status IN ('Scheduled', 'Completed', 'Cancelled')),
        -- Composite key supports a consistent optional link from the visit.
        CONSTRAINT UQ_Appointment_Participants UNIQUE (AppointmentID, PatientID, DoctorID)
    );
    CREATE UNIQUE INDEX UX_Appointment_Doctor_Start
        ON dbo.Appointment (DoctorID, AppointmentDate, AppointmentTime)
        WHERE Status <> 'Cancelled';
    CREATE UNIQUE INDEX UX_Appointment_Patient_Start
        ON dbo.Appointment (PatientID, AppointmentDate, AppointmentTime)
        WHERE Status <> 'Cancelled';
    CREATE INDEX IX_Appointment_Department_Date
        ON dbo.Appointment (DepartmentID, AppointmentDate) INCLUDE (Status);

    CREATE TABLE dbo.Medical_Record (
        RecordID INT NOT NULL CONSTRAINT PK_Medical_Record PRIMARY KEY,
        PatientID INT NOT NULL,
        DoctorID INT NOT NULL,
        VisitDate DATE NOT NULL,
        Diagnosis NVARCHAR(MAX) NULL,
        TreatmentPlan NVARCHAR(MAX) NULL,
        -- Legacy narrative only. dbo.Prescription is the medication source of truth.
        Prescription NVARCHAR(MAX) NULL,
        AppointmentID INT NULL, -- null for walk-ins or unlinked legacy records
        CONSTRAINT FK_Medical_Record_Patient FOREIGN KEY (PatientID) REFERENCES dbo.Patient (PatientID),
        CONSTRAINT FK_Medical_Record_Doctor FOREIGN KEY (DoctorID) REFERENCES dbo.Doctor (DoctorID),
        CONSTRAINT FK_Medical_Record_Appointment FOREIGN KEY (AppointmentID, PatientID, DoctorID)
            REFERENCES dbo.Appointment (AppointmentID, PatientID, DoctorID),
        CONSTRAINT UQ_Medical_Record_Patient UNIQUE (RecordID, PatientID)
    );
    CREATE INDEX IX_Medical_Record_Patient_Date ON dbo.Medical_Record (PatientID, VisitDate);
    CREATE INDEX IX_Medical_Record_Doctor_Date ON dbo.Medical_Record (DoctorID, VisitDate);
    CREATE INDEX IX_Medical_Record_Appointment ON dbo.Medical_Record (AppointmentID)
        WHERE AppointmentID IS NOT NULL;

    CREATE TABLE dbo.Prescription (
        PrescriptionID INT NOT NULL CONSTRAINT PK_Prescription PRIMARY KEY,
        RecordID INT NOT NULL,
        MedicineID INT NOT NULL,
        Dosage NVARCHAR(100) NOT NULL,
        Frequency NVARCHAR(100) NOT NULL,
        Duration NVARCHAR(100) NOT NULL,
        CONSTRAINT FK_Prescription_Record FOREIGN KEY (RecordID) REFERENCES dbo.Medical_Record (RecordID),
        CONSTRAINT FK_Prescription_Medicine FOREIGN KEY (MedicineID) REFERENCES dbo.Medicine (MedicineID),
        CONSTRAINT CK_Prescription_Instructions CHECK (
            LEN(LTRIM(RTRIM(Dosage))) > 0 AND LEN(LTRIM(RTRIM(Frequency))) > 0
            AND LEN(LTRIM(RTRIM(Duration))) > 0
        )
    );
    CREATE INDEX IX_Prescription_Record ON dbo.Prescription (RecordID);
    CREATE INDEX IX_Prescription_Medicine ON dbo.Prescription (MedicineID);

    CREATE TABLE dbo.Billing (
        BillingID INT NOT NULL CONSTRAINT PK_Billing PRIMARY KEY,
        PatientID INT NOT NULL,
        TotalAmount DECIMAL(12, 2) NOT NULL,
        PaymentStatus VARCHAR(10) NOT NULL CONSTRAINT DF_Billing_Status DEFAULT ('Unpaid'),
        PaymentDate DATE NULL,
        PaymentMethod NVARCHAR(50) NULL,
        RecordID INT NULL, -- populated for visit-level attribution; null means unlinked
        CONSTRAINT FK_Billing_Patient FOREIGN KEY (PatientID) REFERENCES dbo.Patient (PatientID),
        CONSTRAINT FK_Billing_Record FOREIGN KEY (RecordID, PatientID)
            REFERENCES dbo.Medical_Record (RecordID, PatientID),
        CONSTRAINT CK_Billing_Amount CHECK (TotalAmount >= 0),
        CONSTRAINT CK_Billing_Status CHECK (PaymentStatus IN ('Paid', 'Unpaid')),
        -- Simple full-payment model; partial payments require a separate payment table.
        CONSTRAINT CK_Billing_Payment CHECK (
            (PaymentStatus = 'Unpaid' AND PaymentDate IS NULL AND PaymentMethod IS NULL)
            OR (PaymentStatus = 'Paid' AND PaymentDate IS NOT NULL AND PaymentMethod IS NOT NULL
                AND LEN(LTRIM(RTRIM(PaymentMethod))) > 0)
        )
    );
    CREATE INDEX IX_Billing_Patient ON dbo.Billing (PatientID);
    CREATE INDEX IX_Billing_Record ON dbo.Billing (RecordID) WHERE RecordID IS NOT NULL;
    CREATE INDEX IX_Billing_Status_Date ON dbo.Billing (PaymentStatus, PaymentDate) INCLUDE (TotalAmount);

    CREATE TABLE dbo.Room_Assignment (
        AssignmentID INT NOT NULL CONSTRAINT PK_Room_Assignment PRIMARY KEY,
        RoomID INT NOT NULL,
        PatientID INT NOT NULL,
        AdmissionDate DATE NOT NULL,
        DischargeDate DATE NULL,
        CONSTRAINT FK_Room_Assignment_Room FOREIGN KEY (RoomID) REFERENCES dbo.Room (RoomID),
        CONSTRAINT FK_Room_Assignment_Patient FOREIGN KEY (PatientID) REFERENCES dbo.Patient (PatientID),
        CONSTRAINT CK_Room_Assignment_Dates CHECK (DischargeDate IS NULL OR DischargeDate >= AdmissionDate)
    );
    CREATE INDEX IX_Room_Assignment_Room_Dates ON dbo.Room_Assignment (RoomID, AdmissionDate, DischargeDate);
    CREATE INDEX IX_Room_Assignment_Patient_Dates ON dbo.Room_Assignment (PatientID, AdmissionDate);
    CREATE INDEX IX_Staff_Department ON dbo.Staff (DepartmentID);
    CREATE INDEX IX_Doctor_Department ON dbo.Doctor (DepartmentID);
    CREATE INDEX IX_Room_Department ON dbo.Room (DepartmentID);

    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
