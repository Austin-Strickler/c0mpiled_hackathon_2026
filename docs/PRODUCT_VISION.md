---
tags: [product, roadmap]
---

# Product vision and roadmap

What we're building, what already exists, and where the next ideas run into
the rules in [[ENGINEERING_DESIGN]] and [[COMPLIANCE_REQUIREMENTS]]. The design
doc is still the source of truth for how things work; this note is the source
of truth for **what we're aiming at** and in what order.

## The pitch

Lawn and landscaping contractors lose jobs and hours to the quote visit: someone
drives out, measures, and writes a price. We replace that visit. The contractor
sets up their service area and prices once; their customers get an instant
quote from a satellite photo of their own yard, and the job goes straight onto
the contractor's list. No rep comes out, and nobody has to call.

**Who pays:** the contractor (B2B). **Who uses it:** the contractor's customers
(homeowners), through the contractor's own link or website.

## The flow, end to end

### Contractor side (dashboard)

1. Signs up and names the company. ✅ Built (`/sign-up`, `/onboarding`)
2. Sets the area it serves: zip codes or a distance around an address. ✅ Built (`/settings/area`)
3. Sets prices: per 1,000 sq ft, flat rates, size tiers, a minimum charge, per region. ✅ Built (`/pricing`, versioned, with publish and rollback)
4. Gets two ways to reach customers. ✅ Built (`/settings/embed`)
   - a one-line widget to embed in its website (`v1.js`), and
   - a standalone page that works in a phone browser, with a QR code to print.
5. Sees incoming requests and accepts, adjusts or declines them. ✅ Built (`/leads`)

### Customer side (widget / hosted page)

1. Opens the contractor's link or widget and picks a service (mowing, and later others).
2. Types the address. ✅ Built (four boxes: street, city, state, zip)
3. Sees a satellite photo of the property and traces the lawn. ✅ Built (Mapbox static image, tap-to-place outline, several areas allowed)
4. Gets an instant price, with tax shown per line. ✅ Built
5. Answers a short questionnaire (frequency, gate access, grass height, pets...). ⬜ Not built; questions TBD
6. **Books the job:** picks a date and confirms, with no phone call. ⬜ Not built. Today the button is "Request service" and creates a lead the contractor still has to act on.

### Where we're going beyond the competition

What everyone else does is still being researched; see "Open questions". Our bet:

- **Request to job, not request to callback.** Most instant-quote tools stop at a price and a lead form. We want the customer to book and the job to land on the contractor's schedule, with no rep in between.
- **Contractor-owned pricing.** Every number comes from the contractor's own rate table, never a model's guess (R20), so they trust the quote enough to let it book automatically.
- **A property record the contractor can reuse.** The outline, the customer's photos and answers stay on file, so the next quote, or a crew briefing, needs no visit.

## Roadmap

Ordered by what we can demo today and what sells.

| # | Feature | Status | Notes and conflicts |
| --- | --- | --- | --- |
| 1 | Dashboard: area, pricing, embed link, hosted page, QR code | Built | Deployed on Amplify |
| 2 | Widget: address, satellite outline, instant price | Built | R15 (Mapbox permission to trace over its imagery) still blocks a real launch, not the demo |
| 3 | Customer questionnaire | Next | Answers go on the lead. Anything that changes the price has to be a priced add-on or tier in the contractor's version, not a free-form multiplier |
| 4 | Instant booking: pick a date, confirm, job on the contractor's list | Next | **Conflicts with R6** (the quote is an estimate; CTA is "request service"; nothing reads as a contract) and **R8** (an accept-and-sign step over $500 needs every HICPA element). Options: (a) "request a date" that the contractor's acceptance confirms, which fits today's rules; (b) true auto-booking for mowing only, after a PA attorney settles R9. Decide and record it in the design doc's Decisions table |
| 5 | Contractor notifications that lead to action (accept / reschedule from the email or text) | Partly built | Email alerts exist (SES); SMS waits on a paid AWS plan and a registered number |
| 6 | Snow shoveling / plowing | Later | Same flow: trace the driveway and walks instead of the lawn. R5: snow taxability must be confirmed before it ships |
| 7 | Photo-based landscaping quotes: customer photographs beds, mulch, shrubs; we estimate mulch area, shrub count, cleanup | Later | **Watch R20:** AI may *measure* (square feet of bed, number of shrubs), but the *price* must still come from the contractor's rate table. Photos are customer data: say so in the privacy policy (R19) |
| 8 | "Improve my yard" suggestions from photos | Later | Same rule: suggestions are fine, prices come from the contractor's services |
| 9 | Before/after images (image generation) of the finished yard | Stretch | Costs per image; label as an illustration, not a promise (R6) |
| 10 | Saved property record / 3D model for the contractor to review remotely | Stretch | **Watch R16:** nothing from Mapbox may be stored, including the outline's geometry. Store only what the customer gave us (their photos, answers, the area in sq ft), or move the tracing to PEMA/NAIP imagery we're allowed to keep (R15) |

## Open questions

- **Competitors.** Who already sells instant lawn quotes to contractors, how do they measure, and do any of them book the job? Fill this in before the pitch.
- **Booking rules.** Option (a) or (b) under roadmap item 4.
- **Questionnaire.** Which questions, and which of them change the price.
- **Pricing model for us.** Per contractor per month, per booked job, or both. Stripe is in the design but not built.
