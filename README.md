# ByteBrain

This is a Next.js template with shadcn/ui.

## Adding components

To add components to your app, run the following command:

```bash
npx shadcn@latest add button
```

This will place the ui components in the `components` directory.

## Using components

To use the components in your app, import them as follows:

```tsx
import { Button } from "@/components/ui/button";
```


## Project Structure

- `backend/app`: Application source code
- `backend/datasets`: Generated CSV datasets (e.g., Timetables, Attendance)
- `backend/analysis`: JSON analysis and schema verification outputs
- `migrations`: SQL migration scripts (01 to 13+)
- `deliverables`: Final project deliverables and reports
- `components`, `hooks`, `lib`: Frontend / UI source code
