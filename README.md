# Leon Backend

Flask API for Leon's ATS-friendly CV builder. It currently manages accounts,
resumes, sections, templates, previews, PDF downloads, job descriptions, and
deterministic ATS analyses. Scores come from keyword coverage and resume
completeness; AI is reserved for optional text-improvement features.

## Render and Supabase deployment

The repository includes a root `render.yaml` with these production commands:

```text
Build: pip install -r backend/requirements.txt
Start: gunicorn --chdir backend app:app --bind 0.0.0.0:$PORT
```

Set `DATABASE_URL` to the Supabase PostgreSQL connection string in Render.
The application accepts `postgresql://` and `postgres://` URLs and uses
`psycopg2-binary`. Set `FRONTEND_URLS` to a comma-separated list containing
the deployed React origin and local development origins.

`GET /api/health` executes `SELECT 1` and returns `healthy` only when the
configured database connection is available.

Expensive AI, PDF, ATS-analysis, login, and registration routes require JWT
authentication where applicable and have route-level rate limits. Set
`RATELIMIT_STORAGE_URI` to a shared Redis URL in production when running more
than one backend instance; the default `memory://` store is suitable only for
a single development or single-instance service.

## Setup

Install dependencies and configure environment variables:

```powershell
cd backend
..\.venv\Scripts\pip install -r requirements.txt
$env:SECRET_KEY = "replace-with-a-long-random-value"
$env:JWT_SECRET_KEY = "replace-with-a-different-long-random-value"
$env:MYSQL_USER = "root"
$env:MYSQL_PASSWORD = "your-password"
$env:MYSQL_DATABASE = "leon"
```

Run the database setup and seed the built-in templates:

```powershell
$env:FLASK_APP = "app"
..\.venv\Scripts\flask db upgrade -d migrations
..\.venv\Scripts\flask seed-templates
..\.venv\Scripts\flask run
```

Set `ADMIN_EMAILS` to a comma-separated list of administrator emails before
using template create, update, or delete endpoints. Templates are global
application configuration, not user-editable content.

## API areas

- `/api/auth`: register, log in, and read the current user
- `/api/resumes`: resume CRUD, HTML preview, and PDF generation/download
- `/api/resumes/:id/{experiences,educations,projects,skills,certificates,languages}`: section CRUD
- `/api/templates`: public template listing; writes require an administrator

Generated PDF records are created only by the server and are stored beneath
`backend/generated_pdfs`; clients cannot choose server file paths.

## Future ATS integration

Do not expose a provider API key to the React app. A future Qwen service
should only rewrite user-selected text (summary, experience bullets, or project
descriptions); it must not control the ATS score.

On Windows, WeasyPrint also needs native GTK/Pango libraries. For deployment,
run this backend in a Linux/Docker image with those system packages installed.
- Gunicorn
- MySQL

## Local setup

1. Create a virtual environment and install dependencies from `requirements.txt`.
2. Copy `.env.example` to `.env` and set your MySQL credentials.
3. Initialize migrations with `flask --app app db init` the first time.
4. Create and apply the initial migration with `flask --app app db migrate -m "initial"` and `flask --app app db upgrade`.
5. Seed the default templates with `flask --app app seed-templates`.
6. Run the API with `flask --app app run --debug` or `python app.py`.

## Auth

- Register and login return a long-lived access token.
- There is no email verification flow in the backend.
- Use `Authorization: Bearer <token>` on protected routes.

## Endpoints

- `GET /api/health`
- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/auth/me`
- `GET /api/resumes`
- `POST /api/resumes`
- `GET /api/resumes/<id>`
- `PATCH /api/resumes/<id>`
- `DELETE /api/resumes/<id>`
- `GET /api/resumes/<id>/preview`
- `POST /api/resumes/<id>/pdf`
- `GET /api/resumes/<id>/pdf/latest`
- `GET /api/resumes/<id>/download`
- `GET /api/templates`
- `GET /api/templates/<id>`
- `POST /api/templates`
- `PATCH /api/templates/<id>`
- `DELETE /api/templates/<id>`
- `GET /api/resumes/<id>/experiences`
- `POST /api/resumes/<id>/experiences`
- `GET /api/resumes/<id>/experiences/<item_id>`
- `PATCH /api/resumes/<id>/experiences/<item_id>`
- `DELETE /api/resumes/<id>/experiences/<item_id>`
- `GET /api/resumes/<id>/educations`
- `POST /api/resumes/<id>/educations`
- `GET /api/resumes/<id>/educations/<item_id>`
- `PATCH /api/resumes/<id>/educations/<item_id>`
- `DELETE /api/resumes/<id>/educations/<item_id>`
- `GET /api/resumes/<id>/projects`
- `POST /api/resumes/<id>/projects`
- `GET /api/resumes/<id>/projects/<item_id>`
- `PATCH /api/resumes/<id>/projects/<item_id>`
- `DELETE /api/resumes/<id>/projects/<item_id>`
- `GET /api/resumes/<id>/skills`
- `POST /api/resumes/<id>/skills`
- `GET /api/resumes/<id>/skills/<item_id>`
- `PATCH /api/resumes/<id>/skills/<item_id>`
- `DELETE /api/resumes/<id>/skills/<item_id>`
- `GET /api/resumes/<id>/certificates`
- `POST /api/resumes/<id>/certificates`
- `GET /api/resumes/<id>/certificates/<item_id>`
- `PATCH /api/resumes/<id>/certificates/<item_id>`
- `DELETE /api/resumes/<id>/certificates/<item_id>`
- `GET /api/resumes/<id>/languages`
- `POST /api/resumes/<id>/languages`
- `GET /api/resumes/<id>/languages/<item_id>`
- `PATCH /api/resumes/<id>/languages/<item_id>`
- `DELETE /api/resumes/<id>/languages/<item_id>`
- `GET /api/resumes/<id>/generated-pdfs`
- `POST /api/resumes/<id>/generated-pdfs`
- `GET /api/resumes/<id>/generated-pdfs/<item_id>`
- `DELETE /api/resumes/<id>/generated-pdfs/<item_id>`

## Resume payload shape

```json
{
  "title": "Software Engineer CV",
  "target_role": "Software Engineer",
  "professional_summary": "...",
  "linkedin_url": "linkedin.com/in/yourname",
  "github_url": "github.com/yourname",
  "portfolio_url": "yourportfolio.com",
  "website_url": "yourwebsite.com",
  "template_name": "modern",
  "ats_score": 82.5,
  "status": "draft",
  "version": 1
}
```
