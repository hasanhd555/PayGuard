# CFPB Consumer Complaint Database — Data Documentation

**Dataset:** Consumer Complaint Database (CCDB) — Historical Archive  
**Publisher:** Consumer Financial Protection Bureau (CFPB), United States  
**Archive period:** September 13 – October 2025  
**Source:** [CFPB Historical Archive](https://files.consumerfinance.gov/f/documents/CCDB_Export_13_September_2025_through_October_2025.zip)  
**Format:** ZIP archive containing CSV data

## 1. Dataset Overview

The Consumer Complaint Database is a publicly available dataset maintained by the Consumer Financial Protection Bureau (CFPB), a United States government agency responsible for consumer protection in financial services.

The dataset contains complaints submitted by consumers regarding financial products and services, including credit reporting, debt collection, credit cards, bank accounts, mortgages, loans, and payment services.

Each row represents an individual consumer complaint. The dataset includes information about the financial product involved, the issue reported, the company associated with the complaint, and the company's response.

Some records also contain a **consumer complaint narrative**, which is a free-text description of the consumer's experience. These narratives are published with consumer consent and after the removal of personally identifying information.

The dataset also includes administrative information such as complaint dates, geographic location, submission method, response status, and unique complaint identifiers.

Complaints represent consumer-reported experiences and do not necessarily indicate verified misconduct by the companies involved.

## 2. Dataset Structure

The dataset is organized in a tabular format, where:

- **Each row** represents one consumer complaint.
- **Each column** represents an attribute of that complaint.
- **Complaint ID** uniquely identifies each record.
- **Consumer complaint narrative** contains unstructured text, while most other columns contain structured categorical, date, or identifier information.

The selected archive contains **16 columns**.

The data types below represent logical data types. Nullable status indicates whether missing or blank values are permitted or expected, rather than the observed completeness of this particular archive.

## 3. Data Dictionary

| # | Column | Data Type | Nullable | Description | Example |
|---|---|---|---|---|---|
| 1 | **Date received** | Date | No, normally | Date the CFPB received the consumer complaint, which may differ from when the issue occurred. | `09/18/2025` |
| 2 | **Product** | String (Categorical) | No, normally | Broad category of financial product or service associated with the complaint. | `Debt collection` |
| 3 | **Sub-product** | String (Categorical) | Yes | More specific financial product classification within the broader product category. | `Telecommunications debt` |
| 4 | **Issue** | String (Categorical) | No, normally | Primary problem reported by the consumer, selected from predefined issue categories. | `Attempts to collect debt not owed` |
| 5 | **Sub-issue** | String (Categorical) | Yes | More detailed classification of the reported issue. Not all issues have sub-issues. | `Debt was paid` |
| 6 | **Consumer complaint narrative** | String (Free Text) | Yes | Consumer's written description of the complaint, published when applicable consent and privacy requirements are satisfied. | `I paid my bill, but the collection agency keeps contacting me...` |
| 7 | **Company public response** | String (Categorical) | Yes | Optional public-facing statement from the company describing its position regarding the complaint. | `Company believes complaint is the result of an isolated error` |
| 8 | **Company** | String (Categorical) | No, normally | Name of the company associated with the complaint. | `Experian Information Solutions Inc.` |
| 9 | **State** | String (Categorical) | Yes | State or territory associated with the consumer's reported mailing address. | `CA` |
| 10 | **ZIP code** | String | Yes | Consumer's mailing ZIP code, which may be partially masked or omitted for privacy. | `10001`, `900XX` |
| 11 | **Tags** | String (Categorical) | Yes | Additional labels identifying certain consumer populations, such as older adults or servicemembers. | `Older American`, `Servicemember` |
| 12 | **Submitted via** | String (Categorical) | No, normally | Channel through which the CFPB received the complaint. | `Web`, `Phone`, `Referral` |
| 13 | **Date sent to company** | Date | No, normally | Date the CFPB forwarded the complaint to the company for a response. | `09/19/2025` |
| 14 | **Company response to consumer** | String (Categorical) | Yes | Company's reported response status or resolution category. | `Closed with explanation`, `In progress` |
| 15 | **Timely response?** | String (Binary Categorical) | Yes | Indicates whether the company responded within the applicable CFPB response timeframe. | `Yes`, `No` |
| 16 | **Complaint ID** | Integer (Identifier) | No | Unique numerical identifier assigned to each consumer complaint. | `32566228` |
