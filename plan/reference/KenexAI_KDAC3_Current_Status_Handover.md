KenexAI (KDAC-3) - Current Project Status & Architecture Handover
Current Progress
• Project rebuilt using Next.js App Router.
• Custom authentication completed.
• Username/password are validated from the PostgreSQL users table.
• Supabase PostgreSQL is connected through direct pg connection.
• Role-based login implemented (Student, Faculty, Admin).
• Successful login redirects to the correct dashboard based on the role.
• Current dashboards are simple placeholders: Welcome to Student Dashboard / Faculty Dashboard / Admin Dashboard.
• Route protection is enabled.
• Root URL redirects to Login when no session exists.
Database
Supabase is currently used as the PostgreSQL database only. The application connects directly using the pg library. Supabase REST API, Supabase Auth and RLS are intentionally not used in the current implementation.
Authentication Flow
Login -> Read username/password from users table -> Validate -> Read role -> Create session -> Redirect to role dashboard.
Architecture Decisions
• Next.js: Authentication, session, UI and dashboards.
• FastAPI (planned): ETL, Analytics, ML and GenAI.
• Python: Pandas, NumPy, Scikit-learn/XGBoost.
• Database: Supabase PostgreSQL.
• UI: tweakcn + shadcn/ui + Tailwind CSS v4.
Development Workflow
Database -> Backend/API -> Business Logic -> Basic Responsive UI -> API Integration -> Testing -> Module Complete
