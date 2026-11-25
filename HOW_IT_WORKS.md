## How it works

**Exposure.** China revenue = annual revenue x China share of revenue. Companies are tiered by share: Low (up to 10%), Moderate (up to 25%), High (up to 40%), Severe (above 40%). Revenue and China shares come from the periods named in the table, which mix annual and quarterly disclosures from 2024 and early 2025; ASML's share is of system sales only. Edit them with the latest filings.

**Breaking point.** The share of China revenue a company can lose before it loses a set share of total revenue (5% by default): breaking point = threshold / China share. A company with 42% of sales in China hits a 5% total revenue loss after losing just 12% of its China business; one with 13% in China can lose 38%. Above 100% means China alone cannot cause that much damage.

**Scenarios.** Each scenario sets the share of China revenue lost for chip designers and for equipment makers, plus how much of that lost revenue is resold to other regions by year 3. Every slider can be changed.

**Profit and value.** Operating profit lost = revenue lost x incremental margin (lost sales carry higher margins than average because fixed costs stay). Value at risk = profit lost x (1 minus a 15% tax rate) x the earnings multiple.

**Recovery path.** Year 1 is the full loss. Net revenue lost in year t = revenue lost x (1 minus recapture x (t minus 1) / 2), so redirected sales ramp up to the full recapture share by year 3.

**Monte Carlo.** For each company, the loss rate is drawn from a beta distribution centered on the scenario value, and the China share moves by a normal shock with the relative standard deviation you set. The app adds the basket's revenue lost in each simulation and reports the mean, median, 5th and 95th percentiles. It measures the year 1 loss before any recovery; loss and share draws are independent, and a 100% loss rate is treated as certain.

**Limits.** This is a scenario tool, not a forecast. Starting figures come from company filings and earnings releases but periods differ and numbers change each quarter. Not investment advice.
