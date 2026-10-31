-- Run after inserts.sql in a disposable user database. Errors fail sqlcmd -b.
SET NOCOUNT ON;
IF (SELECT COUNT(*) FROM dbo.Appointment) <> 4338 THROW 51100, 'Unexpected appointment count.', 1;
IF NOT EXISTS (SELECT 1 FROM dbo.Room_Assignment) THROW 51101, 'Room stays are missing.', 1;
IF EXISTS (SELECT 1 FROM dbo.Appointment a JOIN dbo.Doctor d ON a.DoctorID=d.DoctorID WHERE a.DepartmentID<>d.DepartmentID)
    THROW 51102, 'Generated appointment department mismatch.', 1;
IF EXISTS (SELECT 1 FROM dbo.Medical_Record r JOIN dbo.Appointment a ON r.AppointmentID=a.AppointmentID WHERE a.Status<>'Completed' OR a.AppointmentDate<>r.VisitDate)
    THROW 51103, 'Visits must match a completed appointment date.', 1;
IF EXISTS (SELECT 1 FROM dbo.Room r WHERE
    CASE WHEN EXISTS (SELECT 1 FROM dbo.Room_Assignment a WHERE a.RoomID=r.RoomID AND a.DischargeDate IS NULL) THEN 'Occupied' ELSE 'Available' END <> r.AvailabilityStatus)
    THROW 51104, 'Room snapshot does not match active assignments.', 1;
IF EXISTS (SELECT 1 FROM dbo.Room_Assignment a JOIN dbo.Room_Assignment b ON a.AssignmentID<b.AssignmentID AND (a.RoomID=b.RoomID OR a.PatientID=b.PatientID)
    WHERE a.AdmissionDate<ISNULL(b.DischargeDate,'99991231') AND b.AdmissionDate<ISNULL(a.DischargeDate,'99991231'))
    THROW 51105, 'Room or patient stay overlap.', 1;
DECLARE @Collected DECIMAL(18,2)=(SELECT SUM(TotalAmount) FROM dbo.Billing WHERE PaymentStatus='Paid');
DECLARE @Attributed DECIMAL(18,2)=(SELECT SUM(b.TotalAmount) FROM dbo.Billing b JOIN dbo.Medical_Record r ON b.RecordID=r.RecordID JOIN dbo.Appointment a ON a.AppointmentID=r.AppointmentID JOIN dbo.Department d ON d.DepartmentID=a.DepartmentID WHERE b.PaymentStatus='Paid');
IF @Collected<>@Attributed THROW 51106, 'Collected amount duplicated or lost in service attribution.', 1;
PRINT 'PASS: generated seed loaded; encounters, occupancy, intervals and collected totals reconcile.';
