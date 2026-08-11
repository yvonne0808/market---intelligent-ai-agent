# SEA MedTech Monthly Report Keyword Focus Design

## Objective

Replace the broad business keyword taxonomy used for Southeast Asia Monthly
Report collection with a focused, event-led taxonomy. The collector should
build a high-volume medical-device candidate pool without using Customer
Analysis company or competitor watchlists. Later API/LLM analysis determines
business and packaging relevance.

## Scope

Modify only the Monthly Report keyword configuration and its compatibility
copy:

- `southeast_asia_medtech/monthly_report/config/keywords.yaml`
- `southeast_asia_medtech/config/keywords.yaml`

Do not modify:

- Customer Analysis configuration, prompts, watchlists, or scripts;
- Monthly Report scoring or report-generation prompts;
- source enablement or scraping behavior;
- the existing medical-device packaging keyword category, except when a
  duplicate needs consolidation.

## Keyword Model

Replace the current broad `medical_device_business` list with eight event-led
categories. Chinese labels describe business intent; English phrases and
synonyms support source/API retrieval.

1. **Product approval and launch**
   - important medical devices and consumables approved or launched;
   - registration certificate, market authorization, approval, clearance;
   - high-value consumables, low-value consumables, disposable and single-use
     medical products.
2. **Clinical and registration progress**
   - successful or pivotal clinical trials;
   - registration clinical trials, clinical investigation milestones;
   - regulatory submission and registration application.
3. **Overseas market access**
   - export and overseas expansion;
   - FDA clearance/approval, CE marking, EU MDR certification;
   - overseas registration and market-entry authorization.
4. **Commercialization and channels**
   - product commercialization, commercial launch, sales rollout;
   - market expansion, distributor appointment, channel and distribution
     partnerships.
5. **Financing, M&A and strategic cooperation**
   - material financing, funding, acquisition, merger and strategic investment;
   - BD, licensing, joint venture and strategic cooperation.
6. **Manufacturing, capacity and supply chain**
   - production base, manufacturing facility and factory construction;
   - new production line, line commissioning and capacity expansion;
   - supply-chain investment or change with a concrete device/consumable link.
7. **Sales scale and market size**
   - disclosed revenue, sales volume, commercial ramp-up and shipment growth;
   - quantified medical-device or consumables market size.
8. **Packaging and sterile-supply opportunity**
   - medical-device packaging, sterile packaging and sterile barrier systems;
   - packaging demand created by launch, volume growth, exports or capacity;
   - supply-chain opportunities tied to medical devices or consumables.

## Precision Rules

- Avoid weak standalone terms such as `FDA`, `CE`, `factory`, `investment`,
  `market growth` or `clinical study` when they lack medical-device context.
- Prefer specific phrases such as `medical device FDA clearance`, `CE marked
  medical device`, `medical consumables production line`, or combinations of a
  core device/consumables term and an event term.
- General hospital operations, pharmaceuticals, diseases, wellness, academic
  research without a device product, and generic macroeconomic investment are
  outside scope.
- Company names are extracted from matched articles; they are not required as
  collection inputs.

## Compatibility and Validation

- Both keyword registries must remain byte-identical.
- Every keyword retains the existing schema: keyword, synonyms, weight and
  language.
- Tests must assert the presence of representative phrases from all eight
  groups and the absence of selected weak standalone terms.
- Existing prompt and configuration-loading tests must continue to pass.

## Success Criteria

- Monthly Report discovery is driven by the eight approved event groups.
- Customer/competitor names are not required for a match.
- Packaging terms remain available as an independent relevance signal.
- The taxonomy favors concrete medical-device and consumables events over
  generic policy, hospital, pharmaceutical or market commentary.
