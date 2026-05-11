# EXIM App for ERPNext

**Export-Import Management Solution**  
**Developed by [FinByz Tech Pvt. Ltd.](https://finbyz.tech)**

---

## Overview

The EXIM App for ERPNext streamlines the export-import process by automating every stage — from Proforma Invoice to Export Benefit Claims, Forward Contracts, and License Compliance.  

It ensures compliance, accuracy, and transparency in international trade by minimizing manual work and enabling real-time tracking of export activities.

### Key Objectives
- Automate documentation and compliance workflows  
- Eliminate manual errors and data duplication  
- Improve claim management and currency tracking  
- Ensure LC and license adherence  
- Enhance financial visibility and control  

---

## 1. Setup

### Prerequisites
Before installing the EXIM App, ensure the following:
- ERPNext version 14 or later is installed and running  
- User has System Manager or Administrator role  
- Company and Customer Master are configured in ERPNext  
- Relevant export data fields (ports, incoterms, LC details) are defined  

### Installation

Navigate to your ERPNext bench directory:
```bash
cd ~/frappe-bench
bench get-app exim_app https://github.com/finbyz/exim_app.git
bench --site yoursite.domain install-app exim_app
bench restart


## 2. Initial Configuration

Step 1: Enable EXIM Features
Go to:
Selling > Setup > EXIM Settings

Set preferences for:
Export benefit tracking (RoDTEP, Drawback)
License and LC validation
Default shipping terms and ports

Step 2: Configure Company Export Information
Navigate to:
Accounting > Company

Fill in:
Port of Loading and Discharge
Default Inco Terms
Payment and Shipping Terms
LC Contract linkage settings


## 3. Custom Fields and Compliance

The EXIM App introduces several export-related fields to ERPNext documents to ensure compliance and traceability across the export cycle.

Key Field Additions

Proforma Invoice / Sales Order / Sales Invoice :
Port of Loading / Discharge
Inco Terms
Payment & Shipping Terms
Container & Shipping Line Details

Contract Terms (LC):
LC Number and Terms
Document Requirements and Checks
Compliance Clauses

Export Benefits:
RoDTEP and Drawback Rates
Claim Tracking and Script Numbers
Automatic Journal Entries

Forward Contract:
Contract Number, Amount, and Maturity Date
Utilization and Cancellation Tracking

License Management:
Advance Authorization License Number
Item- and Quantity-based Validation


## 4. Process Flow

Step 1: Proforma Invoice

Create standardized export quotations with all key details:
Port, Payment, and Shipping Terms
Inco Terms and LC references

Convert to Sales Order seamlessly — data auto-flows to later documents.

Step 2: LC Contract Terms:
Link Contract Terms Document with the Sales Order.
Record LC details, document requirements, and clauses to ensure compliance.

Step 3: Invoice & Document Generation:
From the Sales Invoice, navigate to the EXIM section and fill export data.
System auto-generates all key documents:
Commercial Invoice
Packing List
Export Value Declaration
Drawback Declaration
Draft B/L, VGM, and Annexures

Step 4: Export Benefits Tracking:
Automatically calculate and post RoDTEP and Duty Drawback amounts as receivables.
Generate claim documents and track submission status directly from ERPNext.

Step 5: Currency Risk Management:
Maintain and utilize Forward Contracts within Payment Entries.
Track utilization, handle cancellations, and auto-calculate gain/loss.
Receive notifications for upcoming maturity dates.

Step 6: License Compliance:
Record and validate Advance Authorization Licenses for imports/exports.
System prevents over/under utilization and alerts when nearing limits.


## 5. Supported Scenarios:
Multi-currency and multi-country exports
RoDTEP and Drawback claim automation
Forward contract and FX gain/loss tracking
Duty-free import license validation
Compliance with LC and export documentation standards

## 6. Benefits
Operational:
Automated export documentation
LC and license compliance validation
Time-saving with consistent data flow

Financial:
Maximize RoDTEP/Drawback claims
Track government receivables in real-time
Prevent currency losses via forward tracking

Strategic:
Complete export visibility
Inbuilt audit trail and team accountability
Scalable and compliant export operations


## Documentation
Full EXIM App user guide and setup details are available at:
https://finbyz.tech/exim-app


## License
GNU GPL v3 (see license.txt for details)
© FinByz Tech Pvt. Ltd. — All Rights Reserved