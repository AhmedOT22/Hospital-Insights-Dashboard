/* Run after model.sql in a fresh disposable SQL Server database, using sqlcmd -b.
   Fixtures roll back; no dependency on the inconsistent legacy seed file. */
SET NOCOUNT ON;
SET XACT_ABORT OFF; -- expected constraint failures must not doom the fixture transaction
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
SET ANSI_PADDING ON;
SET ANSI_WARNINGS ON;
SET ARITHABORT ON;
SET CONCAT_NULL_YIELDS_NULL ON;
SET NUMERIC_ROUNDABORT OFF;
GO
CREATE PROCEDURE dbo.AssertRejected @Statement NVARCHAR(MAX), @ExpectedError INT
AS
BEGIN
    BEGIN TRY
        EXEC sys.sp_executesql @Statement;
    END TRY
    BEGIN CATCH
        IF ERROR_NUMBER() = @ExpectedError RETURN;
        THROW;
    END CATCH;
    THROW 51000, 'Invalid data was accepted by the schema.', 1;
END;
GO
BEGIN TRY
    BEGIN TRANSACTION;

    IF (SELECT COUNT(*) FROM sys.tables WHERE schema_id = SCHEMA_ID('dbo')) <> 11
        THROW 51001, 'Expected eleven hospital tables.', 1;
    IF EXISTS (SELECT 1 FROM sys.foreign_keys WHERE delete_referential_action <> 0 OR update_referential_action <> 0)
        THROW 51002, 'History must not be cascade-deleted or cascade-updated.', 1;

    INSERT dbo.Department (DepartmentID, DepartmentName) VALUES (1, N'Cardiology'), (2, N'Emergency');
    INSERT dbo.Medicine (MedicineID, MedicineName, Manufacturer, Price) VALUES (1, N'Demo medicine', N'Demo manufacturer', 10);
    -- Missing and shared contact details are legitimate.
    INSERT dbo.Patient (PatientID, FirstName, LastName, DateOfBirth, PhoneNumber)
        VALUES (1, N'Test', N'One', '19900101', '555-0100'), (2, N'Test', N'Two', '20000101', '555-0100'),
               (3, N'Test', N'Three', '20010101', NULL);
    INSERT dbo.Doctor (DoctorID, FirstName, LastName, Specialization, DepartmentID)
        VALUES (1, N'Test', N'Doctor', N'Cardiology', 1), (2, N'Other', N'Doctor', N'Emergency', 2);
    INSERT dbo.Staff (StaffID, FirstName, LastName, Role, DepartmentID) VALUES (1, N'Test', N'Staff', N'Administrator', 1);
    INSERT dbo.Room (RoomID, RoomNumber, DepartmentID, RoomType) VALUES (1, '101', 1, 'Private');
    INSERT dbo.Appointment (AppointmentID, PatientID, DoctorID, DepartmentID, AppointmentDate, AppointmentTime)
        VALUES (1, 1, 1, 1, '20260101', '09:00'), (2, 2, 2, 2, '20260101', '10:00');
    -- Cancellation releases a start slot; it does not delete the appointment.
    INSERT dbo.Appointment (AppointmentID, PatientID, DoctorID, DepartmentID, AppointmentDate, AppointmentTime, Status)
        VALUES (3, 1, 1, 1, '20260101', '09:00', 'Cancelled');
    INSERT dbo.Medical_Record (RecordID, PatientID, DoctorID, VisitDate, AppointmentID)
        VALUES (1, 1, 1, '20260101', 1);
    -- Walk-ins do not need an appointment link.
    INSERT dbo.Medical_Record (RecordID, PatientID, DoctorID, VisitDate) VALUES (2, 2, 2, '20260102');
    INSERT dbo.Prescription (PrescriptionID, RecordID, MedicineID, Dosage, Frequency, Duration)
        VALUES (1, 1, 1, N'Demo dose', N'Demo frequency', N'Demo duration');
    INSERT dbo.Billing (BillingID, PatientID, TotalAmount, RecordID) VALUES (1, 1, 100, 1), (2, 2, 50, NULL);
    UPDATE dbo.Billing SET PaymentStatus='Paid', PaymentDate='20260102', PaymentMethod=N'Card' WHERE BillingID=1;
    INSERT dbo.Room_Assignment (AssignmentID, RoomID, PatientID, AdmissionDate, DischargeDate)
        VALUES (1, 1, 1, '20260101', '20260102');

    EXEC dbo.AssertRejected N'UPDATE dbo.Medicine SET StockQuantity=-1 WHERE MedicineID=1', 547;
    EXEC dbo.AssertRejected N'UPDATE dbo.Medicine SET Price=-1 WHERE MedicineID=1', 547;
    EXEC dbo.AssertRejected N'UPDATE dbo.Medicine SET StockQuantity=NULL WHERE MedicineID=1', 515;
    EXEC dbo.AssertRejected N'UPDATE dbo.Billing SET TotalAmount=-1 WHERE BillingID=1', 547;
    EXEC dbo.AssertRejected N'UPDATE dbo.Billing SET PaymentDate=NULL WHERE BillingID=1', 547;
    EXEC dbo.AssertRejected N'UPDATE dbo.Billing SET PaymentMethod=N'' '' WHERE BillingID=1', 547;
    EXEC dbo.AssertRejected N'UPDATE dbo.Billing SET PaymentDate=''20260102'' WHERE BillingID=2', 547;
    EXEC dbo.AssertRejected N'UPDATE dbo.Billing SET PaymentMethod=N''Card'' WHERE BillingID=2', 547;
    EXEC dbo.AssertRejected N'UPDATE dbo.Billing SET RecordID=1 WHERE BillingID=2', 547;
    EXEC dbo.AssertRejected N'UPDATE dbo.Medical_Record SET AppointmentID=1 WHERE RecordID=2', 547;
    EXEC dbo.AssertRejected N'UPDATE dbo.Medical_Record SET DoctorID=2 WHERE RecordID=1', 547;
    EXEC dbo.AssertRejected N'UPDATE dbo.Staff SET DepartmentID=999 WHERE StaffID=1', 547;
    EXEC dbo.AssertRejected N'UPDATE dbo.Prescription SET MedicineID=999 WHERE PrescriptionID=1', 547;
    EXEC dbo.AssertRejected N'UPDATE dbo.Prescription SET Duration=N'' '' WHERE PrescriptionID=1', 547;
    EXEC dbo.AssertRejected N'UPDATE dbo.Room_Assignment SET DischargeDate=''20251231'' WHERE AssignmentID=1', 547;
    EXEC dbo.AssertRejected N'UPDATE dbo.Room_Assignment SET AdmissionDate=NULL WHERE AssignmentID=1', 515;
    EXEC dbo.AssertRejected N'UPDATE dbo.Room SET AvailabilityStatus=''Invalid'' WHERE RoomID=1', 547;
    EXEC dbo.AssertRejected N'UPDATE dbo.Doctor SET FirstName=N'' '' WHERE DoctorID=1', 547;
    EXEC dbo.AssertRejected N'UPDATE dbo.Appointment SET AppointmentDate=NULL WHERE AppointmentID=1', 515;
    EXEC dbo.AssertRejected N'UPDATE dbo.Appointment SET Status=''Invalid'' WHERE AppointmentID=1', 547;
    EXEC dbo.AssertRejected N'INSERT dbo.Appointment (AppointmentID,PatientID,DoctorID,DepartmentID,AppointmentDate,AppointmentTime) VALUES (4,2,1,1,''20260101'',''09:00'')', 2601;
    EXEC dbo.AssertRejected N'INSERT dbo.Appointment (AppointmentID,PatientID,DoctorID,DepartmentID,AppointmentDate,AppointmentTime) VALUES (4,1,2,2,''20260101'',''09:00'')', 2601;
    EXEC dbo.AssertRejected N'UPDATE dbo.Appointment SET Status=''Completed'' WHERE AppointmentID=3', 2601;
    EXEC dbo.AssertRejected N'DELETE dbo.Doctor WHERE DoctorID=1', 547;
    EXEC dbo.AssertRejected N'DELETE dbo.Patient WHERE PatientID=1', 547;
    EXEC dbo.AssertRejected N'DELETE dbo.Medical_Record WHERE RecordID=1', 547;
    EXEC dbo.AssertRejected N'DELETE dbo.Medicine WHERE MedicineID=1', 547;
    EXEC dbo.AssertRejected N'DELETE dbo.Department WHERE DepartmentID=1', 547;

    UPDATE dbo.Doctor SET IsActive=0, Availability=0 WHERE DoctorID=1;
    IF NOT EXISTS (SELECT 1 FROM dbo.Medical_Record WHERE RecordID=1)
        THROW 51003, 'Deactivation must preserve history.', 1;

    ROLLBACK TRANSACTION;
    PRINT 'PASS: valid linked records, 28 rejection cases and history-preserving deactivation.';
END TRY
BEGIN CATCH
    IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
GO
DROP PROCEDURE dbo.AssertRejected;
