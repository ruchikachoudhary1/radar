# Decisions

A record of the choices in RADAR that had a real alternative, and why this one
was taken. Kept because six months from now the reasoning is the part that gets
forgotten first — the code stays, the argument for it does not.

Each entry states what was decided, why, what it costs, and what was turned
down. The trade-off section matters most: a decision with no cost usually means
the alternatives were not seriously considered.

---

## Hosted Postgres instead of a SQLite file

*4 August 2026*

**Decision:** Store everything in a hosted PostgreSQL database (Neon), reached
through SQLAlchemy, rather than the SQLite file the app started with.

**Why:** Render's free tier gives a container an ephemeral filesystem. It is
wiped on every deploy, every restart, and every cold start after the service
sleeps. SQLite is a file on that filesystem, so every account, resume and
tracked application disappeared overnight — not as a bug, but as the documented
behaviour of the platform. Anything a user is asked to create has to outlive
the container it was created in.

Neon over the alternatives specifically because its free tier does not pause a
project after a week of inactivity. Supabase does, and needs a manual unpause
from a dashboard. For a project whose next visitor might be an interviewer,
"the database is asleep, give me a minute" is not a recoverable moment.

**Trade-off:** A network round trip per query instead of a local file read, and
one more hosted service that can fail independently. Local development would
also have become heavier if it required Postgres — which is why it does not:
`DATABASE_URL` decides the backend, so the same models and the same tests run
against SQLite locally and Postgres in production.

**Rejected:** Render persistent disks (paid tier only). Render's own free
Postgres (expires 30 days after creation, which would strand the project right
before it was needed). Keeping SQLite and accepting the data loss — briefly
considered, discarded once accounts existed, because losing a user's password
is different from losing a cache.

---

## A deterministic engine underneath every AI feature

*Ongoing, from the first version*

**Decision:** Every feature that calls a language model has a rule-based
implementation underneath it. The rules decide what is true — which gaps exist,
which keywords matched, what the score is. The model only decides how it reads.

**Why:** Two reasons, and the second is the one that matters.

The first is availability: the app is fully functional with no API key. If the
key is missing, the quota is spent, or the response comes back malformed, the
rule layer produces the output instead. Nothing is ever unavailable because a
third party is having a bad day.

The second is honesty. A resume tool that invents experience is worse than
useless — it is actively harmful to the person using it, who will be asked
about that experience in an interview. Because the rules own the facts, the
tailoring engine can only reorder and re-emphasise skills the profile already
contains. It cannot add one. Where a cover letter would be stronger with a
number the profile does not have, both engines are instructed to leave a marked
`[add detail]` placeholder, and the count is shown to the user rather than
hidden.

**Trade-off:** Every AI feature is written twice. The rule-based version of the
cover letter writer is roughly as much code as the prompt, and both have to be
kept in step when the output format changes.

**Rejected:** Calling the model directly and trusting the output, which is
faster to build and the common approach. Also rejected: asking the model to
score the resume. Scores would vary between runs on identical input and could
not be explained to the user, which defeats the point of a rubric.

---

## Passwords and sessions built rather than bought

*4 August 2026*

**Decision:** Hash passwords with bcrypt and issue signed JWTs, rather than
adopting a managed authentication provider.

**Why:** Authentication is the part of a web application most worth
understanding properly, and delegating it would have meant not learning it.
bcrypt because it is deliberately slow and salts every digest: slowness is the
feature, since it is what makes a stolen table expensive to attack, and salting
means two users with the same password do not share a hash. Stateless tokens
because the server then keeps no session state, which matters on a free tier
that restarts containers frequently — an in-memory session store would sign
everyone out on every restart.

**Trade-off:** A signed token cannot be revoked before it expires. There is no
"sign out everywhere". The expiry is therefore 14 days rather than months, which
is a blunt mitigation rather than a fix; a token denylist in Redis would be the
real answer once there is more than one process to share it with.

The login throttle has the same shape: it is a dictionary in one process, so it
resets on restart and would not be shared across instances. Correct for a single
container, wrong the moment there are two.

**Rejected:** Neon Auth and Supabase Auth. Both would have worked and taken
less time. Turned down because the reasoning above is the thing worth being
able to explain, and a managed provider replaces it with a configuration step.

---

## TF-IDF instead of embeddings

*Decided early; corpus corrected 7 August 2026*

**Decision:** Match resumes to job descriptions with TF-IDF vectorisation and
cosine similarity rather than semantic embeddings.

**Why:** Every number traces back to a word that appears in the document, so
the UI can show exactly which terms drove a match and which were missing. That
is the whole premise of the project — a score a user can argue with. Embeddings
would give a number nobody can decompose. TF-IDF also needs no API call and no
model download, so it runs instantly and offline, which keeps it consistent
with the rule-engine decision above.

**Trade-off:** It matches words, not meaning. A resume saying "frontend" and a
posting asking for "React" score no similarity from those terms alone, even
though a human reader would connect them. This is the clearest limitation in
the project and the obvious upgrade path if semantic matching were needed.

**Correction made 7 August 2026:** the vectoriser was originally fitted on just
the resume and the job description. IDF over two documents is not merely weak
but inverted — a term appearing in both scores *lower* than one appearing in
one, which is backwards for similarity. It is now fitted across the 21 role
skill banks alongside the two documents, taking a representative comparison
from 2 distinct IDF values to 11. The corpus is still small; a production
system would derive IDF from thousands of real resumes and postings.

**Rejected:** Sentence-transformer embeddings with a vector store, which solves
the synonym problem and costs explainability, a model download and a dependency
that cannot run in a free tier's memory footprint. Plain keyword counting, which
is explainable but treats every term as equally important.
