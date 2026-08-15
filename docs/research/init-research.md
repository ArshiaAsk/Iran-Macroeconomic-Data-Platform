<div dir="ltr" align="left">

# 📊 Comprehensive Documentation for the Design and Implementation of an Analytical Dashboard for Iran's Macroeconomic Indicators

**Designed for Data Engineers, Data Scientists, and Machine Learning Engineers**

---

## 📋 Table of Contents

1. [Project Introduction and Vision](#1-project-introduction-and-vision)
2. [Key Performance Indicators (KPIs & Metrics) Architecture](#2-key-performance-indicators-kpis--metrics-architecture)
3. [Comprehensive Evaluation of Data Sources (Domestic & International)](#3-comprehensive-evaluation-of-data-sources-domestic--international)
4. [Data Access Table and Direct Links](#4-data-access-table-and-direct-links)
5. [Data Engineering Challenges and Practical Solutions](#5-data-engineering-challenges-and-practical-solutions)

---

## 1. Project Introduction and Vision

Analyzing Iran's macroeconomy presents unique challenges due to structural inflation, significant exchange rate volatility, international sanctions, and periodic changes in statistical base years. These factors make financial modeling and economic forecasting heavily dependent on a **robust and integrated data architecture**.

The primary challenge of this project is not merely creating visual dashboards, but rather **collecting, cleaning, synchronizing heterogeneous time frequencies (Resampling/Interpolation), and constructing consistent chain-linked time series** from multiple—and often incompatible—data sources.

This document serves as the **Specification Document** for implementing the complete data pipeline and analytical dashboard.

---

## 2. Key Performance Indicators (KPIs & Metrics) Architecture

To build a comprehensive 360-degree macroeconomic dashboard, the indicators are organized into **nine primary analytical domains**:

|  No.  | Analytical Domain                            | Key Performance Indicators (KPIs)                                                                                                            |      Frequency      |              Unit             |            Importance for ML Modeling            |
| :---: | :------------------------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------- | :-----------------: | :---------------------------: | :----------------------------------------------: |
| **1** | **Inflation & Prices**                       | Headline CPI, Monthly Inflation (MoM), Year-over-Year Inflation (YoY), Annual Inflation, Producer Price Index (PPI), Income-Decile Inflation |       Monthly       |        Percent / Index        |        **Very High** (Target & Regressor)        |
| **2** | **National Accounts (GDP)**                  | Gross Domestic Product (with oil / excluding oil), Gross Fixed Capital Formation, Sectoral Value Added (Industry, Services, Agriculture)     |  Quarterly / Annual |          Billion IRR          |    **High** (Macroeconomic Growth Measurement)   |
| **3** | **Monetary & Banking Variables**             | Monetary Base ($M_0$), Money Supply ($M_2$), Money Multiplier, Quasi-Money, Interbank Interest Rate, Outstanding Loans & Deposits            | Monthly / Quarterly |     Billion IRR / Percent     | **Very High** (Primary Driver of Inflation & FX) |
| **4** | **Labor Market & Employment**                | Unemployment Rate, Labor Force Participation Rate, Underemployment Rate, Graduate Unemployment Rate                                          |      Quarterly      |            Percent            |                    **Medium**                    |
| **5** | **Foreign Exchange, Gold & Housing Markets** | Free Market USD Exchange Rate, NIMA / FX Center Rate, Emami Gold Coin Price, 18K Gold Price, Coin Premium, Average Tehran Housing Price      |   Daily / Monthly   |         IRR / Percent         |         **Very High** (Liquidity Signal)         |
| **6** | **Foreign Trade**                            | Non-Oil Export Value & Volume, Customs Imports, Trade Balance, Estimated Crude Oil Exports                                                   |   Monthly / Annual  | Million USD / Barrels per Day |        **High** (Foreign Currency Supply)        |
| **7** | **Government Budget & Fiscal Position**      | Tax Revenue, Oil Revenue, Operational Budget Deficit, Government Debt to the Central Bank & Banking System                                   |   Monthly / Annual  |          Billion IRR          |      **High** (Structural Deficit Analysis)      |
| **8** | **Capital Market (Stock Exchange)**          | TEDPIX Index, Equal-Weighted Index, Retail Trading Value, Market P/E Ratio, Market Capitalization                                            |        Daily        |       Index Points / IRR      |          **High** (Market Expectations)          |
| **9** | **Welfare & Income Distribution**            | Gini Coefficient, Top-to-Bottom Income Decile Ratio, Poverty Line Rate                                                                       |        Annual       |     Coefficient / Percent     |                    **Medium**                    |

---

## 3. Comprehensive Evaluation of Data Sources (Domestic & International)

### 🔴 1. Domestic Data Sources (Granular & Regional Data / No Official API)

#### 🔹 Statistical Center of Iran (SCI)

* **Data Coverage:** Official source for CPI, unemployment statistics, national accounts (GDP), and Household Budget Survey (HBS).
* **Advantages:** Highly detailed data (provincial and income-decile breakdowns), standardized statistical methodology.
* **Limitations:** Data is published primarily as Excel files, PDFs, or HTML tables; no official REST API; changes in statistical base years are introduced without providing chain-linked historical series.

#### 🔹 Central Bank of the Islamic Republic of Iran (CBI - TSD System)

* **Data Coverage:** Monetary and banking variables, economic indicators, Tehran housing market, balance of payments.
* **Advantages:** Primary provider of monetary aggregates ($M_0$, $M_2$) and interbank interest rates.
* **Limitations:** Several-month publication delays for certain datasets; occasional suspension of sensitive economic data releases; legacy TSD user interface.

#### 🔹 Tehran Securities Exchange Technology Management Company (TSETMC)

* **Data Coverage:** Daily and intraday capital market data, TEDPIX index, trading value, P/E ratio.
* **Advantages:** Highly accurate and structured market data; accessible through unofficial Python tools and APIs such as `TseClient` and `finpy-tse`.

#### 🔹 Iran Open Data (HBSIR)

* **Data Coverage:** Raw and structured Iranian household budget and expenditure datasets.
* **Advantages:** Provides a Python package for transforming raw Statistical Center of Iran data into analysis-ready DataFrames.

---

### 🔵 2. International Data Sources (Robust APIs / Annual Frequency & Publication Delays)

#### 🔹 World Bank Open Data

* **Data Coverage:** More than 50 years of Iran's macroeconomic time series (GDP, trade, population, energy, etc.).
* **Advantages:** Official and well-maintained Python API (`world_bank_data`); internationally standardized data formats.
* **Limitations:** Data is available only at an **annual frequency** and is typically published with a one- to two-year delay.

#### 🔹 International Monetary Fund (IMF DataMapper & World Economic Outlook)

* **Data Coverage:** Iran's macroeconomic indicators, including **medium-term projections and forecasts** for up to five years.
* **Advantages:** Direct API access along with CSV/JSON downloads; highly valuable as external features for forecasting models.

#### 🔹 U.S. Energy Information Administration (EIA) & Organization of the Petroleum Exporting Countries (OPEC)

* **Data Coverage:** Iran's crude oil production, OPEC basket prices, and estimated oil exports.
* **Advantages:** Reliable monthly and annual energy statistics for the Iranian economy.

---

## 4. Data Access Table and Direct Links

| Data Source                           | Variables                                |       Format      | Extraction Method                   | Direct Access                                       |
| :------------------------------------ | :--------------------------------------- | :---------------: | :---------------------------------- | :-------------------------------------------------- |
| **CBI TSD System**                    | Monetary Base, Liquidity, Housing Market | Excel / Web Table | Web Scraping / Python `pandas`      | https://tsd.cbi.ir                                  |
| **Statistical Center of Iran**        | CPI, Unemployment, GDP                   |    Excel / PDF    | Web Scraping / `pdfplumber`         | https://www.amar.org.ir                             |
| **International Monetary Fund (IMF)** | Inflation, GDP Growth, Forecasts         |  JSON / CSV / API | REST API / Direct Download          | https://www.imf.org/external/datamapper/profile/IRN |
| **World Bank Open Data**              | 50-Year Iran Time Series                 |  API / CSV / JSON | Python `world_bank_data`            | https://data.worldbank.org/country/iran-islamic-rep |
| **Tehran Stock Exchange (TSETMC)**    | TEDPIX, Trading Value                    |     Web / API     | Python `finpy-tse` / `TseClient`    | http://tsetmc.com                                   |
| **TGJU (Gold & Currency Network)**    | Free Market USD, Gold Coins, Gold Prices |        HTML       | Python `requests` + `BeautifulSoup` | https://www.tgju.org                                |
| **Iran Open Data (HBSIR)**            | Household Income & Expenditure           |   Python Library  | `pip install hbsir`                 | https://github.com/Iran-Open-Data/HBSIR             |

---

## 5. Data Engineering Challenges and Practical Solutions

### ⚠️ 1. Base Year Changes and Time Series Discontinuities

* **Challenge:** The Statistical Center of Iran and the Central Bank periodically revise the base year used for calculating CPI and GDP (e.g., from 2011 to 2016, and later to 2021). These revisions introduce abrupt structural breaks and discontinuities into historical time series.
* **ML/Data Engineering Solution:** Apply **Chain Indexing** techniques. Instead of directly using raw index values, calculate growth rates and reconstruct continuous historical series based on the latest base year.

---

### ⚠️ 2. Frequency Mismatch Across Data Sources

* **Challenge:** Gold and foreign exchange data are available daily, inflation is reported monthly, unemployment and GDP are quarterly, while World Bank data is only annual.
* **Solution:**

  * **Downsampling:** Aggregate daily observations into monthly values using averages, closing prices, or volatility measures.
  * **Upsampling / Interpolation:** Convert quarterly or annual data into monthly frequency using methods such as Spline Interpolation or the Denton Method while minimizing the risk of data leakage.

---

### ⚠️ 3. Lack of Official REST APIs for Domestic Institutions

* **Solution:** Design **automated data scrapers** using Python with tools such as `playwright` or `selenium`, combined with scheduled Cron Jobs to periodically download newly published Excel files and upload them into the database staging bucket.

---

*Developed as the technical specification for implementing a data pipeline and analytical dashboard for monitoring and forecasting Iran's macroeconomic indicators.*

</div>
