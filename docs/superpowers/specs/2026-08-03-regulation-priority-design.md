# Regulation Priority Design

## Goal

Lower the default priority of policy and regulation news in both Pharma and
Medical Device monthly-report prompts.

## Design

Add an explicit priority rule to both monthly prompts. Pure policy, regulatory,
guideline, standard, pharmacopoeia, and price-policy interpretation is
background information. It belongs in category summaries or Other News and
must not independently occupy an Executive Summary bullet, top ranking, or
featured opportunity.

The rule does not remove regulation news. A regulatory item may be mentioned
when the structured article explicitly also reports a packaging-material,
packaging-format, production-capacity, procurement-award, commercial-volume,
or customer-business consequence. In that case, the commercial consequence,
not the policy announcement, is the reason for inclusion.

Executive-summary priority becomes: direct packaging signal; commercial launch,
volume, procurement award, factory/capacity, supply-chain or customer signal;
product approval or dosage/form factor with business impact; BD/customer
development. Policy/regulation is last.

## Scope

Modify only the two monthly prompt files. Do not change article-analysis
prompts, data, current reports, or website files.
