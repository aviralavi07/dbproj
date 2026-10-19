# Launch checklist

This project runs on localhost for the course demonstration. It must not be put on the internet until every item below is done.

| Item | Status |
|---|---|
| Favicon added (favicon.ico, 32 px PNG and touch icon in `static/`, linked on every page) | Done |
| Privacy Policy page (`/privacy`) linked from every footer | Done |
| Terms and Conditions page (`/terms`) linked from every footer | Done |
| No "made with" or AI tag anywhere on the pages (checked by test SC12) | Done |
| No stock or AI-generated photos; only the project's own diagrams and screenshots | Done |
| No fake reviews, fake customer counters or invented figures; numbers shown come from the database or the project | Done |
| No scripts, scroll animation or cursor effects (checked by test SC10) | Done |
| No gradients, pill shapes, emoji, icons, em dashes or en dashes (checked by tests SC07, SC08, SC11) | Done |
| Custom domain connected | Not done. Needs a host with a public address, then a DNS record from the domain provider |
| HTTPS certificate | Not done. Needed together with the domain |
| Login for the application | Not done. The application has no login, so it must stay on localhost until this is added |
| Real contact address in the Privacy Policy | Not done. The policy points to the team page for now |
| Replace the Flask development server with a production server and set a private SECRET_KEY | Not done |
