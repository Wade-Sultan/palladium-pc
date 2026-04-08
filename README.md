# Palladium

Building a PC is one of the most satisfying things you can do as a gamer, but the barrier to entry is high. Strict compatibility requirements, questions about how much you really need, and the sheer volume of options make it easy to overspend, underspec, or just give up.

Most AI PC builders take in a use case and budget and call it done, making guesses without enough information ("gaming" can mean anything from being able to run Valorant to playing it at 360+ fps) or confidently recommending parts that are flat-out wrong for the job (like an AMD GPU for someone who wants to train AI models locally). Palladium runs a structured selection pipeline with hard compatibility enforcement, choosing components in the order that actually matters. Along the way, it explains the reasoning: target frame rates, resolution tradeoffs, performance expectations for your specific use case. The result is a build that fits exactly what you'll use it for, without spending more than necessary.

Tell Palladium what you want to do with your PC. It'll handle the rest. Available now in beta at [palladiumtech.ai](https://palladiumtech.ai).

## Technology Stack

- Frontend: Next.js, React, Tailwind CSS, shadcn/ui
- Backend: FastAPI, SQLAlchemy, Alembic
- Admin: Elixir, Phoenix, Backpex
- Database: PostgreSQL
- LLM: Claude (Haiku)
- Cloud: GCP, Vercel

## Upcoming Features

- User authentication and chat history
- PC building guides
- Find a builder map to locate PC builder businesses near you to help put the parts together
- Upgraded part recommendation pipeline
- Real Amazon and Ebay links to buy parts, along with the ability to subscribe to e-mail updates regarding price/availability
