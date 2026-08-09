**Haan bhai, \*\*ye 10 ideas main properly check kiye\*\*. Aur honestly, ye previous 25 se important difference create karte hain: pehle wale features mostly \*\*“student ka data samjhao”\*\* the, ye wale \*\*“student ki daily problem solve karo”\*\* hain.**



**KDAC-3 ka actual objective sirf dashboard banana nahi hai — academic performance analyze karke \*\*learning gaps identify karna, at-risk students detect karna, trends predict karna aur career guidance improve karna\*\* hai. Isliye daily-life assistance layer add karna product ko much stronger banayega.** 



**## 🔥 Main architecture ab aisa hona chahiye**



**```text**

&#x20;                   **KDAC-3 Student Module**

&#x20;                          **│**

&#x20;         **┌────────────────┼────────────────┐**

&#x20;         **↓                ↓                ↓**

&#x20;    **UNDERSTAND         IMPROVE          ACT**

&#x20;         **│                │                │**

&#x20;   **Dashboards         Analytics       Daily Assistance**

&#x20;   **Trends             Risk            Eligibility**

&#x20;   **Performance        Learning Gap    Recovery Plan**

&#x20;   **Attendance         Career          Faculty Query**

&#x20;         **│                │                │**

&#x20;         **└────────────────┼────────────────┘**

&#x20;                          **↓**

&#x20;                   **Student 360**

&#x20;                          **↓**

&#x20;                 **Personal Action Plan**

**```**



**# 🆕 Final Daily-Life Assistance Layer**



**Main tumhare 10 ideas ko thoda improve karke \*\*10 proper product features\*\* bana raha hoon.**



**---**



**# 26. 🎓 Exam Eligibility Checker**



**\*\*Must-have P0.\*\***



**Current schema already supports:**



**\* `attendance.eligibility\_status`**

**\* `attendance.shortage\_flag`**

**\* `attendance.attendance\_percentage`**

**\* `attendance.total\_classes`**

**\* `attendance.attended\_classes`**



**Student ko exam ke time surprise nahi milna chahiye.**



**### UI**



**```text**

**Exam Eligibility**



**┌──────────────────────────────────────┐**

**│ Deep Learning                    ✓    │**

**│ Eligible                             │**

**│ Attendance: 84%                      │**

**└──────────────────────────────────────┘**



**┌──────────────────────────────────────┐**

**│ Natural Language Processing      ⚠   │**

**│ At Risk                              │**

**│ Attendance: 68%                      │**

**│ Required: 75%                        │**

**│                                      │**

**│ \[View Recovery Plan]                 │**

**└──────────────────────────────────────┘**

**```**



**Aur \*\*important\*\*:**



**> Eligibility status backend authoritative hoga. Frontend apna random calculation karke final eligibility decide nahi karega.**



**---**



**# 27. 🚨 Attendance Recovery Plan**



**Ye \*\*Attendance Calculator ka upgraded version\*\* hoga.**



**Calculator:**



**> "Kitni classes attend karni hain?"**



**Recovery Plan:**



**> \*\*"Exactly kya karna hai aur kab tak karna hai?"\*\***



**Example:**



**```text**

**NLP Attendance Recovery**



**Current**

**68%  • 17 / 25**



**Required**

**75%**



**Eligibility deadline**

**20 Aug 2026**



**Upcoming classes**

**6**



**Required attendance**

**5 / 6**



**You can miss**

**1 class**



**⚠ Missing 2 or more may keep you**

**below the eligibility threshold.**



**Upcoming:**

**18 Aug  • NLP • Slot 2**

**19 Aug  • NLP • Slot 1**

**20 Aug  • NLP • Slot 2**

**```**



**### Data stitching**



**```text**

**attendance**

&#x20;     **+**

**daily\_attendance\_07**

&#x20;     **+**

**weekly\_timetable\_07**

&#x20;     **↓**

**Recovery Plan**

**```**



**Ye KDAC-3 ke data-stitching concept ka \*\*real user-facing example\*\* ban jayega.**



**---**



**# 28. 📚 Backlog Clearance Roadmap**



**`attempt\_number` + `result\_status` ka actual useful use.**



**```text**

**Backlog Center**



**⚠ Natural Language Processing**



**Attempt       1**

**Result        Failed**

**Last Score    42%**



**Weakest:**

**End-sem performance**



**Suggested preparation:**

**6 weeks**



**\[View Subject Performance]**

**\[Create Study Plan]**

**```**



**### But important**



**\*\*Supplementary exam date database me available nahi hai\*\*, to system fake date nahi dikhayega.**



**Instead:**



**```text**

**Next reattempt date**

**Not available**



**Check official academic calendar.**

**```**



**Later Admin module se actual supplementary schedule connect kar sakte hain.**



**---**



**# 29. 💬 Ask Faculty / Doubt Box**



**Ye genuinely student-friendly feature hai.**



**Existing:**



**`student\_subject\_enrollment.faculty\_id`**



**se course faculty identify ho sakta hai.**



**### UI**



**```text**

**Ask Faculty**



**Deep Learning**

**Course Faculty: Rahul Patel**



**┌────────────────────────────────────┐**

**│ Type your question...              │**

**│                                    │**

**└────────────────────────────────────┘**



**\[Send Question]**

**```**



**History:**



**```text**

**Your Questions**



**✓ Answered**

**Will Unit 4 be included?**



**Rahul Patel**

**"Yes, Unit 3 and Unit 4."**



**2 days ago**

**```**



**### New table required**



**Something like:**



**```text**

**student\_faculty\_queries**



**query\_id**

**student\_id**

**faculty\_id**

**subject\_id**

**question**

**answer**

**status**

**created\_at**

**answered\_at**

**```**



**Later Admin can audit unanswered queries.**



**---**



**# 30. 🎓 Scholarship \& Financial Opportunity Finder**



**\*\*Idea good hai, but isko carefully implement karna hai.\*\***



**`category`, `admission\_quota` etc. se \*\*eligibility hints\*\* generate kar sakte hain.**



**But:**



**❌ "You are definitely eligible."**



**nahi.**



**Instead:**



**> \*\*"You may qualify based on the information available."\*\***



**```text**

**Scholarship Opportunities**



**Possible matches**



**🏆 Merit Scholarship**

**Reason:**

**CGPA meets displayed merit threshold**



**🏠 EWS Scholarship**

**Reason:**

**Category information may match**



**\[View Requirements]**

**```**



**### Important**



**Actual scholarship rules institution/state specific hote hain.**



**Isliye scholarship rules ko later:**



**```text**

**Admin → Scholarship Rules**

**```**



**se configurable banana better hai.**



**---**



**# 31. ❤️ Gentle Student Wellbeing Check-in**



**Isko \*\*bahut carefully\*\* design karna hai.**



**`lifestyle\_survey` ke:**



**\* `stress\_level`**

**\* `mental\_wellbeing`**



**ko student-facing support ke liye use kar sakte hain.**



**But:**



**### NEVER**



**```text**

**You are depressed.**

**```**



**or**



**```text**

**AI detected mental health problem.**

**```**



**### Instead**



**```text**

**Semester Check-in**



**You've reported higher stress recently.**



**If you're finding the semester difficult,**

**consider talking to someone you trust.**



**\[Contact Student Counselor]**

**\[Talk to Mentor]**

**\[Review My Schedule]**

**```**



**No diagnosis.**



**No faculty exposure by default.**



**No risk score.**



**\*\*Student control mandatory.\*\***



**---**



**# 32. 🕐 Smart Free-Slot Study Suggestions**



**This one mujhe \*\*bahut pasand hai\*\* because existing timetable se directly possible hai.**



**```text**

**Today's Schedule**



**13:00  Deep Learning**

**14:00  Free**

**15:00  NLP**

**16:00  Free**

**```**



**System:**



**```text**

**💡 Smart suggestion**



**14:00–15:00 is free.**



**NLP is currently your weakest**

**subject this week.**



**Suggested:**

**Revise NLP — 45 min**



**\[Start Study Session]**

**```**



**### Data**



**```text**

**weekly\_timetable\_07**

&#x20;      **+**

**performance**

&#x20;      **+**

**attendance**

&#x20;      **↓**

**Study suggestion**

**```**



**No GenAI required initially.**



**---**



**# 33. 🌐 Language \& Accessibility Mode**



**Definitely add.**



**Initially:**



**```text**

**English**

**हिन्दी**

**ગુજરાતી**

**```**



**But \*\*database values and academic terminology shouldn't be translated incorrectly\*\*.**



**For example:**



**```text**

**CGPA**

**SGPA**

**Internal Marks**

**Mid-sem**

**End-sem**

**Attendance**

**```**



**can remain consistent.**



**Only UI/help text changes.**



**### Architecture**



**```text**

**i18n/**

&#x20;**├── en.json**

&#x20;**├── hi.json**

&#x20;**└── gu.json**

**```**



**And:**



**```text**

**English | हिन्दी | ગુજરાતી**

**```**



**in Student Settings.**



**---**



**# 34. 📶 Data Saver / Lightweight Mode**



**This is a very good \*\*India-first usability feature\*\*.**



**Normal:**



**```text**

**Charts**

**Animations**

**Graphs**

**Images**

**```**



**Data Saver:**



**```text**

**75% Attendance**

**8.1 CGPA**

**3 subjects need attention**

**2 upcoming classes**

**```**



**No unnecessary heavy charts.**



**### Important**



**Don't create two completely separate UIs.**



**Same data:**



**```text**

**Normal UI**

&#x20;    **↓**

**Presentation layer**



**Data Saver**

&#x20;    **↓**

**Light presentation layer**

**```**



**---**



**# 35. 👨‍👩‍👦 Student-Controlled Guardian Sharing**



**Good idea, but \*\*strict consent\*\*.**



**Default:**



**```text**

**Guardian Sharing**

**OFF**

**```**



**Student chooses:**



**```text**

**☑ Monthly academic summary**

**☐ Attendance alerts**

**☐ Performance alerts**

**```**



**Preview:**



**```text**

**Guardian will receive:**



**Attendance: 78%**

**CGPA: 8.1**

**Subjects needing attention: 1**



**\[Cancel] \[Enable Sharing]**

**```**



**Never automatically expose:**



**\* lifestyle**

**\* stress**

**\* mental wellbeing**

**\* private faculty conversations**

**\* risk explanations**



**unless there is an explicit, institution-approved policy and consent flow.**



**---**



**# 💥 Ab main tumhare liye aur 10 ideas add karunga**



**Ye tumhare current list me directly nahi the, aur mujhe lagta hai \*\*real student life ke liye ye aur powerful hain.\*\***



**---**



**# 36. 📅 Student Academic Calendar**



**One place:**



**```text**

**Academic Calendar**



**12 Aug**

**Mid-sem starts**



**18 Aug**

**NLP eligibility review**



**25 Aug**

**Assignment deadline**



**02 Sep**

**End-sem starts**

**```**



**But assignment/exam dates ke liye \*\*new academic calendar data source/table\*\* chahiye.**



**Admin eventually maintain karega.**



**---**



**# 37. 🔔 Smart Student Notification Center**



**Not random notifications.**



**Only useful things:**



**```text**

**🔴 Action Required**

**NLP attendance below eligibility**



**🟡 Upcoming**

**Mid-sem begins in 5 days**



**🔵 Academic**

**New marks published**



**🟢 Update**

**Faculty answered your question**

**```**



**This also prepares us for the Admin notification system you discussed earlier.**



**---**



**# 38. 📊 "What Changed Since Yesterday?"**



**This is a \*\*very student-friendly feature\*\*.**



**Student opens dashboard:**



**```text**

**Since your last visit**



**+ Deep Learning marks published**

**+ Attendance updated for NLP**

**⚠ NLP attendance dropped 2%**

**+ Faculty answered your question**

**```**



**Instead of student checking everything manually.**



**---**



**# 39. 🧭 Today's Student Brief**



**One compact daily card:**



**```text**

**Good Morning, Aarav 👋**



**Today**



**13:00  Deep Learning**

**15:00  NLP**



**Focus**

**⚠ NLP attendance: 68%**



**Free time**

**14:00–15:00**



**Priority**

**Revise NLP for 45 min**



**Upcoming**

**Mid-sem in 6 days**

**```**



**\*\*This could become the main Student Home experience.\*\***



**---**



**# 40. 📝 Attendance Discrepancy Report**



**Student notices:**



**> "I was present but it shows absent."**



**Instead of WhatsApp faculty:**



**```text**

**Attendance Issue?**



**NLP**

**09 Aug**

**Status: Absent**



**\[Report an issue]**

**```**



**Student:**



**```text**

**Reason:**

**I attended this lecture.**



**Additional note:**

**"I was present but marked absent."**

**```**



**Faculty gets:**



**```text**

**Attendance Correction Request**

**```**



**Then:**



**```text**

**Pending → Approved / Rejected**

**```**



**This would use your existing:**



**`attendance\_change\_log`**



**as audit infrastructure, but needs a \*\*request/workflow table\*\*.**



**---**



**# 41. 🔥 Attendance Streak / Consistency**



**Using `daily\_attendance\_07`:**



**```text**

**Attendance Consistency**



**🔥 8 consecutive classes attended**



**This month**

**Present: 23**

**Absent: 2**

**```**



**Don't make it childish/gamified too much.**



**Keep it professional.**



**---**



**# 42. 📈 Personal Improvement Tracker**



**Instead of only grades:**



**```text**

**Your Progress**



**Attendance      ↑ 68 → 74**

**Performance     ↑ 61 → 69**

**Backlogs        ↓ 2 → 1**

**Credits earned  ↑ 18 → 22**

**```**



**Student sees \*\*improvement\*\*, not only current score.**



**---**



**# 43. 🎯 Personal Academic Goals**



**Student can set:**



**```text**

**My Goals**



**🎯 Maintain 75%+ attendance**

**Progress: 82%**



**🎯 SGPA > 8**

**Progress: 7.6**



**🎯 Clear NLP backlog**

**Status: In progress**

**```**



**This is student-owned, unlike system risk.**



**---**



**# 44. 🧠 Study Session Mode**



**Student clicks:**



**```text**

**\[Start Study Session]**

**```**



**gets:**



**```text**

**NLP**

**45 minutes**



**Today's target:**

**End-sem Unit 3**



**\[Start]**

**```**



**At end:**



**```text**

**Session completed ✓**



**45 minutes**

**NLP**



**\[Mark topic completed]**

**```**



**This can initially be completely client-side/local.**



**No AI needed.**



**---**



**# 45. 🏆 Personal Achievement Timeline**



**Different from document vault.**



**```text**

**My Academic Journey**



**2024**

**✓ Semester 3 completed**



**2025**

**✓ Internship completed**



**2026**

**✓ NLP project completed**

**✓ Semester 7 started**



**2026**

**🎯 Placement readiness: 72%**

**```**



**This gives students a \*\*sense of progress\*\*, not just analytics.**



**---**



**# 🏆 So now our Student Module becomes 45 capabilities**



**But bhai \*\*45 ka matlab 45 screens nahi hai.\*\***



**That's very important.**



**We should group them into \*\*8 student experiences\*\*:**



**```text**

**STUDENT MODULE**

**│**

**├── 🏠 1. Home / Today**

**│      ├─ Today's Brief**

**│      ├─ Smart Alerts**

**│      ├─ What Changed**

**│      └─ Action Plan**

**│**

**├── 📚 2. Academics**

**│      ├─ Subject Overview**

**│      ├─ Marks**

**│      ├─ Trends**

**│      ├─ Learning Gaps**

**│      ├─ Benchmarks**

**│      └─ What-if Simulator**

**│**

**├── 🟢 3. Attendance**

**│      ├─ All Subjects**

**│      ├─ Eligibility**

**│      ├─ Recovery Plan**

**│      ├─ Calculator**

**│      ├─ Calendar**

**│      ├─ Forecast**

**│      └─ Discrepancy Request**

**│**

**├── 🎯 4. Success**

**│      ├─ Risk**

**│      ├─ Focus Areas**

**│      ├─ Goals**

**│      ├─ Improvement**

**│      └─ Action Plan**

**│**

**├── 💼 5. Career**

**│      ├─ Readiness**

**│      ├─ Career Gap**

**│      ├─ Achievements**

**│      └─ Portfolio**

**│**

**├── 🧑‍🏫 6. Support**

**│      ├─ Ask Faculty**

**│      ├─ Mentor**

**│      ├─ Backlog Roadmap**

**│      └─ Counselor**

**│**

**├── 📅 7. Planning**

**│      ├─ Timetable**

**│      ├─ Academic Calendar**

**│      ├─ Free Slots**

**│      └─ Study Sessions**

**│**

**└── ⚙️ 8. Student Control**

&#x20;      **├─ Privacy / Consent**

&#x20;      **├─ Guardian Sharing**

&#x20;      **├─ Language**

&#x20;      **├─ Data Saver**

&#x20;      **└─ Notifications**

**```**



**## 🔥 Aur sabse important — implementation order**



**\*\*Sab 45 ek saath nahi banayenge.\*\***



**### Phase 1 — Student Foundation**



**\* Student Home**

**\* All Subject Overview**

**\* Marks**

**\* Attendance**

**\* Timetable**

**\* Academic Profile**



**### Phase 2 — Real Daily Utility**



**\* Exam Eligibility**

**\* Recovery Plan**

**\* Attendance Calculator**

**\* Attendance Calendar**

**\* Today's Brief**

**\* Smart Notifications**

**\* Free Slot Suggestions**

**\* Backlog Roadmap**

**\* Faculty Query**



**### Phase 3 — Advanced Analytics**



**\* Performance Trend**

**\* Learning Gap**

**\* Cohort Benchmark**

**\* Cross-Cohort Trend**

**\* Academic Health**

**\* Attendance Forecast**

**\* Focus Areas**

**\* Improvement Tracker**



**### Phase 4 — Student Success**



**\* Risk Explanation**

**\* Mentor Loop**

**\* Intervention**

**\* Goals**

**\* Action Plan**



**### Phase 5 — Career**



**\* Career Readiness**

**\* Career Gap**

**\* Achievement Vault**

**\* Portfolio**



**### Phase 6 — Responsible + Inclusive**



**\* Privacy/Consent**

**\* Data Transparency**

**\* Guardian Sharing**

**\* Hindi/Gujarati**

**\* Data Saver**

**\* Accessibility**



**### Phase 7 — Advanced / Optional**



**\* Peer Study Groups**

**\* Study Session Mode**

**\* Achievement Timeline**

**\* Advanced ML**

**\* GenAI**



**---**



**## 🧠 One final important decision**



**\*\*Student Module ka main philosophy ab ye hona chahiye:\*\***



**> \*\*Don't just tell the student what is happening. Tell them what it means, what they should do, and help them do it.\*\***



**Example:**



**❌ Old ERP:**



**> Attendance = 68%**



**🟡 KenexAI Analytics:**



**> Attendance = 68%, below threshold.**



**🟢 \*\*KDAC-3 Student Experience:\*\***



**> \*\*Attendance = 68%\*\***

**> You may be at risk for exam eligibility.**

**> \*\*5 of your next 6 NLP classes need to be attended to reach the target.\*\***

**> \*\*Next class: Tomorrow, 2 PM.\*\***

**> `\[View Recovery Plan]`**



**\*\*Ye difference hi KenexAI ko normal college ERP se genuinely alag karega.\*\***



**Aur jo sensitive lifestyle/wellbeing data hai, usko \*\*analytics ke naam par freely expose nahi karna\*\* — privacy, consent, access control aur explainability ko architecture ka first-class part rakhna chahiye. This also aligns with the project's documented emphasis on role-based access, privacy/security and explainable intelligence.** 



**\*\*Mere hisab se ab Student Module ka functional scope freeze kar sakte hain: 45 capabilities, 8 experiences, phased implementation. Iske baad feature-addition se pehle existing flow ko production-ready karna better rahega.\*\***


















**Haan bhai, \*\*ye batch genuinely different hai\*\*. Previous ideas me hum mostly existing data ko analyze kar rahe the; ab ye fields aur workflows \*\*Student Module ke missing practical layer\*\* ko fill kar rahe hain.**



**Aur mujhe lagta hai inko add karna chahiye — \*\*lekin thoda improve karke\*\*, taki unnecessary feature-bloat na ho.**



**# 🔥 In 9 ideas ka proper evaluation**



**| # | Feature                     | Value | Data available?     | New DB?     | Priority  |**

**| - | --------------------------- | ----- | ------------------- | ----------- | --------- |**

**| 1 | Component-Level Weak Area   | ⭐⭐⭐⭐⭐ | Yes\*                | No          | \*\*P0\*\*    |**

**| 2 | Attendance Dispute          | ⭐⭐⭐⭐⭐ | Audit + attendance  | Yes         | \*\*P0\*\*    |**

**| 3 | Marks Correction Request    | ⭐⭐⭐⭐⭐ | Performance + audit | Yes         | \*\*P0\*\*    |**

**| 4 | Repeat-Attempt Support      | ⭐⭐⭐⭐⭐ | `attempt\_number`\*   | No          | \*\*P1\*\*    |**

**| 5 | Emergency Info Card         | ⭐⭐⭐⭐  | Yes                 | No          | \*\*P1\*\*    |**

**| 6 | Digital Student ID + QR     | ⭐⭐⭐⭐  | Yes                 | No          | \*\*P1\*\*    |**

**| 7 | Elective Advisor            | ⭐⭐⭐⭐⭐ | Mostly yes          | Maybe later | \*\*P1\*\*    |**

**| 8 | Regional Study Buddy        | ⭐⭐⭐   | Yes                 | Yes         | \*\*P2\*\*    |**

**| 9 | Assignment/Deadline Tracker | ⭐⭐⭐⭐⭐ | No                  | Yes         | \*\*P0/P1\*\* |**



**`\*` Important: `ct1\_marks`, `ct2\_marks`, and `attempt\_number` \*\*exist in schema\*\*, but actual populated values should be verified before building analytics around them. We should never treat NULL as zero.**



**---**



**# 1. 🧠 Component-Level Weak-Area Detector — DEFINITELY ADD**



**Ye mujhe is batch ka \*\*#1 feature\*\* lagta hai.**



**Current:**



**```text**

**Overall Percentage = 64%**

**```**



**isn't enough.**



**We can show:**



**```text**

**NLP — Assessment Analysis**



**CT1          16 / 20     80%**

**CT2          12 / 20     60%**

**Mid-sem      28 / 50     56%**

**End-sem      —           Not entered**



**Assessment Trend**

**80% → 60% → 56%**



**⚠ Declining performance**

**```**



**But \*\*important improvement\*\*:**



**System ko automatically bolna nahi chahiye:**



**> "You have a concept retention issue."**



**unless ML/analytics evidence actually supports that.**



**Instead V1:**



**> \*\*"Your performance has declined across successive assessments."\*\***



**Then:**



**> "End-sem and Mid-sem currently show the largest gap compared with CT assessments."**



**Later ML/GenAI can interpret the pattern.**



**### Aur ek powerful comparison:**



**```text**

**Your Assessment Performance**



&#x20;            **You     Cohort Avg**

**CT1          80%       76%**

**CT2          60%       72%**

**Mid-sem      56%       70%**



**⚠ Largest gap: Mid-sem**

**```**



**Ye \*\*granular learning-gap analytics\*\* ban jayega.**



**---**



**# 2. 🛡️ Attendance Dispute — MUST HAVE**



**Ye genuinely real-world feature hai.**



**Student:**



**```text**

**Attendance**



**07 Aug**

**Deep Learning**

**Absent**



**\[Report an issue]**

**```**



**Click:**



**```text**

**Report Attendance Issue**



**Date: 07 Aug**

**Subject: Deep Learning**

**Status: Absent**



**Reason:**

**\[ I attended this lecture ]**



**Additional details:**

**\[\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_]**



**\[Submit Request]**

**```**



**Then:**



**```text**

**Pending Review**

**```**



**Faculty side:**



**```text**

**Attendance Correction Requests**



**Aarav Patel**

**Deep Learning**

**07 Aug**



**Reason:**

**"I attended this lecture."**



**\[Review]**

**```**



**Faculty:**



**```text**

**Approve → attendance correction**

**Reject → reason required**

**```**



**### Important architecture**



**`attendance\_change\_log` \*\*audit trail hai\*\*, dispute workflow nahi.**



**So:**



**```text**

**attendance\_disputes**

**```**



**new table is correct.**



**Possible fields:**



**```text**

**dispute\_id**

**student\_id**

**subject\_id**

**attendance\_id**

**lecture\_date**

**reason**

**student\_comment**

**status**

**faculty\_id**

**faculty\_response**

**created\_at**

**reviewed\_at**

**```**



**And approval ke baad \*\*existing canonical attendance correction flow\*\* use hoga.**



**No direct student UPDATE to attendance.**



**---**



**# 3. 📝 Marks Recheck / Correction Request — MUST HAVE**



**Same architecture:**



**```text**

**Grievance Center**

&#x20;      **│**

&#x20;      **├── Attendance Issue**

&#x20;      **│**

&#x20;      **└── Marks Recheck**

**```**



**Student:**



**```text**

**Deep Learning**



**Mid-sem**

**38 / 50**



**\[Request Recheck]**

**```**



**Then:**



**```text**

**Reason:**

**I believe my marks may have been entered incorrectly.**



**\[Submit]**

**```**



**Faculty:**



**```text**

**Pending**

**↓**

**Review**

**↓**

**Approve / Reject**

**```**



**### Important**



**Student \*\*actual marks directly edit nahi karega\*\*.**



**Only:**



**```text**

**Student Request**

&#x20;       **↓**

**Faculty Review**

&#x20;       **↓**

**Approved**

&#x20;       **↓**

**Existing marks update flow**

&#x20;       **↓**

**performance\_change\_log**

**```**



**This is much more secure and production-grade.**



**---**



**# 4. 🔁 Repeat-Attempt Support**



**Very good use of:**



**`attempt\_number`**



**But UI should not punish/embarrass students.**



**Instead:**



**```text**

**NLP**



**Current Attempt: 2**



**Previous Attempt**

**──────────────────**

**CT1        12/20**

**CT2        10/20**

**Mid-sem    20/50**

**End-sem    18/70**



**Previous Result**

**Failed**



**Areas needing attention**

**──────────────────**

**Mid-sem     40%**

**End-sem     26%**

**```**



**Then:**



**> \*\*Your previous strongest component was CT1. The largest performance gap was in End-sem.\*\***



**That's objective.**



**### Then:**



**```text**

**Suggested Preparation**



**1. Focus on cumulative concepts**

**2. Practice previous-paper style questions**

**3. Review topics where assessment performance dropped**

**```**



**No fake recommendation.**



**---**



**# 5. 🆘 Emergency Info Card**



**Good, but \*\*privacy rules mandatory\*\*.**



**Student profile:**



**```text**

**Emergency Information**



**Blood Group**

**O-**



**Emergency Contact**

**Aryan Shah**



**Contact**

**XXXXXXXXXX**

**```**



**But:**



**### Student view**



**Student can see their own data.**



**### Faculty/Staff**



**Only authorized staff roles should see emergency details.**



**### Never expose publicly.**



**And I would \*\*not put the full phone number prominently on the normal dashboard\*\*.**



**Maybe:**



**```text**

**Emergency Contact**

**Aryan Shah**

**••••••••4208**



**\[Reveal]**

**```**



**This is safer.**



**---**



**# 6. 🪪 Digital Student ID + QR**



**\*\*Great demo feature.\*\***



**```text**

**┌───────────────────────────────┐**

**│         KENEXAI               │**

**│                               │**

**│       \[ Student Photo ]       │**

**│                               │**

**│       Aarav Patel             │**

**│       CSE · Semester 7        │**

**│       2023010003              │**

**│                               │**

**│          \[ QR CODE ]          │**

**│                               │**

**│       Active Student          │**

**└───────────────────────────────┘**

**```**



**### QR should NOT contain sensitive information.**



**Don't encode:**



**```text**

**DOB**

**blood group**

**phone**

**email**

**```**



**Instead encode a signed/opaque verification token.**



**Example concept:**



**```text**

**QR**

&#x20;**↓**

**Verification endpoint**

&#x20;**↓**

**Student ID verified**

&#x20;**↓**

**Display only authorized public academic identity**

**```**



**This makes it much more production-ready.**



**---**



**# 7. 🎯 Next-Semester Elective Advisor**



**\*\*Very strong KDAC-3 feature\*\* because it connects:**



**```text**

**Academic Performance**

&#x20;       **+**

**Career Preferences**

&#x20;       **+**

**Subjects**

&#x20;       **↓**

**Elective Recommendation**

**```**



**Example:**



**```text**

**Your Career Goal**

**AI / ML Engineer**



**Your Strengths**

**Deep Learning      82%**

**NLP                78%**



**Recommended Electives**



**🟢 Advanced Machine Learning**

**Strong career alignment**



**🟢 Cloud Computing**

**Useful for ML deployment**



**🟡 Data Engineering**

**Good complementary skill**

**```**



**But don't say:**



**> "Take this subject."**



**Better:**



**> \*\*"Recommended based on your academic performance and stated career preference."\*\***



**And show \*\*why\*\*.**



**---**



**# 8. 🌍 Regional Study Buddy**



**Good idea but \*\*P2\*\*.**



**Because:**



**`city`, `domicile\_state`**



**can be used for matching, but location/privacy makes this more sensitive.**



**I would NOT show:**



**> "3 students from Ahmedabad: Rahul, Jay, X."**



**Instead:**



**```text**

**Study / Commute Groups**



**3 students in your cohort**

**selected Ahmedabad as their city.**



**\[Explore Opt-in Groups]**

**```**



**Only after explicit opt-in:**



**```text**

**You joined:**

**Ahmedabad Study Group**

**```**



**No automatic location sharing.**



**---**



**# 9. 📅 Assignment \& Deadline Tracker — HIGH VALUE**



**This one actually deserves \*\*P0/P1\*\*.**



**Because the current system tells:**



**> marks**

**> attendance**

**> timetable**



**but doesn't help with:**



**> \*\*what do I have to submit and when?\*\***



**Add:**



**```text**

**assignments**

**```**



**Possible structure:**



**```text**

**assignment\_id**

**subject\_id**

**faculty\_id**

**title**

**description**

**assigned\_date**

**due\_date**

**max\_marks**

**semester\_no**

**academic\_year**

**status**

**created\_at**

**updated\_at**

**```**



**Student side:**



**```text**

**Upcoming**



**🔴 NLP Assignment 2**

**Due Tomorrow**



**🟡 Deep Learning Project**

**Due 15 Aug**



**🟢 DBMS Assignment**

**Due 20 Aug**

**```**



**And:**



**```text**

**\[Mark as Submitted]**

**```**



**Later faculty can actually create/manage assignments.**



**This becomes a \*\*real academic workflow\*\*, not just analytics.**



**---**



**# 🔥 Ab ek aur feature main in ideas se naturally derive karunga**



**## 10. 🔔 Deadline + Attendance + Exam "Conflict Detector"**



**This is \*\*very KenexAI\*\*.**



**Suppose:**



**```text**

**Tomorrow**



**10:00 NLP lecture**

**13:00 Assignment deadline**

**15:00 Deep Learning**

**```**



**System:**



**> ⚠️ You have two academic commitments tomorrow.**



**Or:**



**```text**

**Exam Eligibility Deadline**

**+**

**Attendance Recovery**

**+**

**Upcoming Classes**

**```**



**Then:**



**> \*\*You need to attend the next 3 NLP sessions before the eligibility review date.\*\***



**This combines multiple datasets instead of just displaying them separately.**



**---**



**# 🔥 And one more: Student Academic Timeline**



**All major events in one timeline:**



**```text**

**Academic Timeline**



**08 Aug**

**✓ NLP attendance updated**



**09 Aug**

**✓ Deep Learning marks published**



**10 Aug**

**⚠ Attendance eligibility warning**



**12 Aug**

**📅 NLP Assignment due**



**20 Aug**

**🎓 Eligibility review**

**```**



**This can become the foundation for the \*\*Today's Brief / What Changed\*\* features we discussed earlier.**



**---**



**# 🧩 Now the Student Module is becoming really strong**



**Instead of thinking:**



**> "45 features + 9 more = 54 random features"**



**we should think in \*\*functional systems\*\*:**



**```text**

&#x20;                   **STUDENT MODULE**

&#x20;                         **│**

&#x20;**┌────────────────────────┼────────────────────────┐**

&#x20;**↓                        ↓                        ↓**

**ACADEMICS              ATTENDANCE               CAREER**

&#x20;**↓                        ↓                        ↓**

**Marks                   Eligibility             Readiness**

**Trends                  Recovery                 Gap Analysis**

**Weak Areas              Calculator               Electives**

**What-if                 Calendar                 Portfolio**

**Backlog                 Forecast**

&#x20;                         **│**

&#x20;                         **↓**

&#x20;                   **STUDENT SUPPORT**

&#x20;                         **│**

&#x20;            **┌────────────┼────────────┐**

&#x20;            **↓            ↓            ↓**

&#x20;        **Faculty       Grievance     Mentor**

&#x20;         **Query         Center        Loop**

&#x20;            **│            │            │**

&#x20;            **└────────────┼────────────┘**

&#x20;                         **↓**

&#x20;                   **DAILY ASSISTANCE**

&#x20;                         **│**

&#x20;           **┌─────────────┼─────────────┐**

&#x20;           **↓             ↓             ↓**

&#x20;      **Timetable      Deadlines      Daily Brief**

&#x20;      **Free Slots     Assignments    Notifications**

**```**



**---**



**# 🏆 My final priority ranking**



**### 🔴 P0 — Build first**



**1. \*\*Component-Level Weak Area\*\***

**2. \*\*Exam Eligibility Checker\*\***

**3. \*\*Attendance Recovery Plan\*\***

**4. \*\*Attendance Dispute\*\***

**5. \*\*Marks Recheck Request\*\***

**6. \*\*Assignment/Deadline Tracker\*\***

**7. \*\*Today's Academic Brief\*\***

**8. \*\*Student Notifications\*\***



**### 🟠 P1 — Next**



**9. \*\*Repeat-Attempt Support\*\***

**10. \*\*Elective Advisor\*\***

**11. \*\*Digital Student ID + QR\*\***

**12. \*\*Emergency Info Card\*\***

**13. \*\*Backlog Roadmap\*\***

**14. \*\*Free Slot Study Suggestions\*\***

**15. \*\*Academic Timeline\*\***



**### 🟡 P2 — Later**



**16. Regional Study Buddy**

**17. Advanced study-session features**

**18. More social/engagement features**



**---**



**## 💡 Aur ek important correction**



**`ct1\_marks` / `ct2\_marks` ko lekar hum \*\*abhi UI build nahi karenge sirf isliye ki columns exist karte hain\*\*.**



**Pehle actual live DB me:**



**```text**

**ct1\_marks**

**ct2\_marks**

**```**



**ki population check karenge.**



**Agar values genuinely available hain → \*\*Component Weak-Area Detector immediately build\*\*.**



**Agar mostly `NULL` hain → UI me:**



**> CT1 — Not entered**

**> CT2 — Not entered**



**dikhayenge.**



**\*\*NULL ko 0 kabhi nahi treat karenge.\*\***



**Same `attempt\_number` ke saath.**



**---**



**### Aur mujhe sabse strong combination ye lag raha hai:**



**\*\*Grievance Center + Eligibility + Recovery + Weak Area + Assignment Deadline\*\***



**because then student ke paas ek complete loop hoga:**



**```text**

**Problem detected**

&#x20;     **↓**

**Student understands problem**

&#x20;     **↓**

**System gives exact action**

&#x20;     **↓**

**Student can request help**

&#x20;     **↓**

**Faculty/mentor responds**

&#x20;     **↓**

**Student tracks resolution**

**```**



**\*\*Ye KDAC-3 ko "analytics dashboard" se genuinely "Student Academic Success Platform" bana deta hai.\*\***



**Aur existing `performance\_change\_log` / `attendance\_change\_log` ko audit layer hi rakhenge; student grievance ko direct canonical table modification ka shortcut nahi denge. This preserves the existing auditability pattern.** 








**Haan bhai. \*\*Is baar implementation nahi karna hai — sirf complete implementation blueprint finalize karna hai.\*\* Maine existing Student plan, current project status, live-schema findings, Faculty Marks/Attendance implementation reports, current API architecture aur shared UI architecture ko cross-check kiya hai. Existing Student Module already has the core 7 pages and 3 FastAPI read APIs, while the newer Faculty Marks/Attendance flows now write canonical academic data and audit those changes.**  



**\*\*No code/database change is proposed or performed in this response.\*\***



**---**



**# KDAC-3 Student Module — Complete Implementation Plan**



**## 0. Final architectural decision**



**The Student Module will remain:**



**> \*\*READ-ONLY academic surface + student-facing analytics/intelligence layer.\*\***



**Students \*\*cannot\*\* directly modify:**



**\* marks**

**\* attendance**

**\* grades**

**\* SGPA/CGPA**

**\* semester summaries**

**\* academic status**

**\* risk predictions**

**\* faculty-entered records**



**The existing architecture already separates Next.js as Interface/Access, FastAPI as Intelligence/Data, and Supabase PostgreSQL as the system of record.** 



**For any future student-request workflow such as attendance dispute or marks recheck:**



**```text**

**Student**

&#x20;  **↓**

**CREATE REQUEST**

&#x20;  **↓**

**Faculty/Admin review**

&#x20;  **↓**

**Approved**

&#x20;  **↓**

**Existing academic write flow**

&#x20;  **↓**

**Canonical table**

**```**



**Never:**



**```text**

**Student → UPDATE attendance/marks**

**```**



**---**



**# 1. Current Architecture Analysis**



**## Existing architecture**



**```text**

**Student Browser**

&#x20;     **│**

&#x20;     **▼**

**Next.js 16**

**├── Student pages**

**├── BFF routes**

**├── Session / requireRole**

**└── UI components**

&#x20;     **│**

&#x20;     **▼**

**FastAPI :8000**

**├── API**

**├── Service**

**├── Repository**

**├── Authorization**

**└── Threshold Engine**

&#x20;     **│**

&#x20;     **▼**

**Supabase PostgreSQL**

**```**



**Current project uses direct PostgreSQL access through `pg` and `asyncpg`; Supabase REST/Auth/RLS are not the core access mechanism.** 



**The backend follows:**



**```text**

**Repository**

&#x20;   **↓**

**Service**

&#x20;   **↓**

**API**

&#x20;   **↓**

**BFF**

&#x20;   **↓**

**Student UI**

**```**



**The existing Student planning document explicitly requires backend-first → BFF → UI and says business logic should not be computed in the frontend.** 



**### Existing Student routes**



**| Route                    | Current purpose     | Future        |**

**| ------------------------ | ------------------- | ------------- |**

**| `/student/dashboard`     | Overview            | Upgrade       |**

**| `/student/academic`      | Semester history    | Upgrade       |**

**| `/student/subjects`      | Subject performance | Upgrade       |**

**| `/student/attendance`    | Attendance          | Major upgrade |**

**| `/student/profile`       | Read-only profile   | Upgrade       |**

**| `/student/notifications` | Placeholder         | Implement     |**

**| `/student/settings`      | Placeholder         | Later         |**



**The current Student Module already has these pages and three FastAPI Student APIs.** 



**### Current API mapping**



**Existing contract:**



**```text**

**GET /api/v1/students/me/profile**

**GET /api/v1/students/me/academic-summary**

**GET /api/v1/students/me/performance**

**```**



**BFF mapping is already defined through:**



**```text**

**app/api/student/profile**

**app/api/student/dashboard**

**app/api/student/academic-summary**

**app/api/student/performance**

**app/api/student/attendance**

**```**



**The Student plan confirms these existing mappings.** 



**---**



**# 2. Existing Database / Table Mapping**



**This is the most important part.**



**## Master relationship**



**```text**

**students**

&#x20;  **│**

&#x20;  **├──────── student\_semester\_summary**

&#x20;  **│**

&#x20;  **├──────── career\_preferences**

&#x20;  **│**

&#x20;  **├──────── lifestyle\_survey**

&#x20;  **│**

&#x20;  **├──────── faculty\_student\_map**

&#x20;  **│**

&#x20;  **├──────── risk\_predictions**

&#x20;  **│**

&#x20;  **└──────── users**

&#x20;        



**student\_subject\_enrollment**

&#x20;  **│**

&#x20;  **├──────── student\_subject\_performance**

&#x20;  **│**

&#x20;  **└──────── attendance**



**daily\_attendance\_07**

&#x20;  **│**

&#x20;  **└──────── lecture-level attendance**



**weekly\_timetable\_07**

&#x20;  **│**

&#x20;  **└──────── schedule reference**

**```**



**`student\_id` is the canonical person/stitching key, while `enrollment\_record\_id` is the important academic-grain key connecting enrollment → performance → attendance.** 



**---**



**## 2.1 `students`**



**### Provides**



**\* identity**

**\* enrollment**

**\* department**

**\* current semester**

**\* academic year**

**\* CGPA**

**\* overall percentage**

**\* overall attendance**

**\* credits**

**\* backlogs**

**\* academic standing**

**\* contact/profile data**



**### Used for**



**\* Student profile**

**\* Dashboard identity**

**\* Academic overview**

**\* Quick stats**

**\* Academic standing**

**\* Emergency information later**



**### Primary join**



**```text**

**students.student\_id**

**```**



**### Joins**



**```text**

**students.student\_id**

&#x20;   **↓**

**student\_subject\_enrollment.student\_id**

**student\_semester\_summary.student\_id**

**career\_preferences.student\_id**

**lifestyle\_survey.student\_id**

**faculty\_student\_map.student\_id**

**risk\_predictions.student\_id**

**```**



**This is the \*\*Student 360 anchor\*\*.**



**---**



**# 2.2 `student\_subject\_enrollment`**



**### Provides**



**\* enrolled subjects**

**\* subject code/name**

**\* semester**

**\* academic year**

**\* credits**

**\* subject type**

**\* faculty**

**\* enrollment status**



**### Used for**



**\* My Subjects**

**\* current subjects**

**\* subject details**

**\* faculty mapping**

**\* career/elective matching**

**\* joining performance and attendance**



**### Primary join**



**```text**

**enrollment\_record\_id**

**```**



**### Critical joins**



**```text**

**student\_subject\_enrollment.enrollment\_record\_id**

&#x20;     **=**

**student\_subject\_performance.enrollment\_record\_id**



**student\_subject\_enrollment.enrollment\_record\_id**

&#x20;     **=**

**attendance.enrollment\_record\_id**

**```**



**This is the \*\*academic bridge table\*\*.**



**---**



**# 2.3 `student\_subject\_performance`**



**### Provides**



**```text**

**internal\_marks**

**mid\_sem\_marks**

**end\_sem\_marks**

**total\_marks**

**percentage**

**grade**

**grade\_point**

**result\_status**

**attempt\_number**

**performance\_category**

**remarks**

**ct1\_marks**

**ct2\_marks**

**updated\_at**

**updated\_by**

**```**



**### Used for**



**\* Marks display**

**\* Subject performance**

**\* Grade**

**\* Performance trend**

**\* Component-level weak-area analysis**

**\* Learning-gap detection**

**\* Repeat-attempt analysis**

**\* Marks simulator**

**\* Academic comparison**

**\* ML features**



**### Important rule**



**```text**

**NULL ≠ 0**

**```**



**If End-sem is NULL:**



**```text**

**End-sem → Not Published / Not Entered**

**Total → Not Calculated**

**Grade → —**

**```**



**The current live data actually contains many NULL End-sem values, so the Student Module must preserve this state rather than fabricate zeroes.** 



**---**



**# 2.4 `attendance`**



**This is the \*\*student-facing aggregate attendance source\*\*.**



**### Provides**



**\* total classes**

**\* attended classes**

**\* percentage**

**\* attendance status**

**\* eligibility status**

**\* shortage flag**

**\* remarks**



**### Used for**



**\* Overall attendance**

**\* Subject attendance**

**\* Eligibility**

**\* Attendance calculator**

**\* Attendance risk band**

**\* Attendance alerts**



**### Join**



**```text**

**attendance.enrollment\_record\_id**

&#x20;     **=**

**student\_subject\_enrollment.enrollment\_record\_id**

**```**



**Because `attendance` itself does not carry all semester/year context, scope through enrollment rather than inventing filters.**



**---**



**# 2.5 `daily\_attendance\_07`**



**This is lecture-level data.**



**### Provides**



**\* date**

**\* subject**

**\* faculty**

**\* lecture number**

**\* day**

**\* P/A status**

**\* semester**

**\* academic year**



**### Used for**



**\* Daily attendance history**

**\* Attendance calendar**

**\* Attendance drill-down**

**\* Attendance timeline**

**\* Attendance forecast**

**\* Attendance dispute evidence**

**\* "What changed?" notifications**



**It is now the canonical lecture-level attendance source for Faculty Attendance Entry and is reconciled into aggregate `attendance`.** 



**---**



**# 2.6 `student\_semester\_summary`**



**### Provides**



**\* subjects registered**

**\* credits**

**\* credits earned**

**\* semester marks**

**\* semester percentage**

**\* SGPA**

**\* grade**

**\* attendance**

**\* backlog count**

**\* semester result**

**\* academic standing**



**### Used for**



**\* Academic page**

**\* SGPA trend**

**\* semester trend**

**\* CGPA/SGPA overview**

**\* backlog trend**

**\* cohort trend**

**\* academic health**

**\* performance history**



**### Join**



**```text**

**student\_id**

**+**

**semester\_no**

**+**

**academic\_year**

**```**



**This is a \*\*semester-grain derived table\*\*.**



**Important: current Marks Entry updates subject-level performance immediately, but semester summary is ETL-owned and may not refresh until the derivation process runs. The existing plan explicitly documents this limitation.** 



**Therefore the Student UI needs a freshness indicator for semester-level data until ETL is live.**



**---**



**# 2.7 `weekly\_timetable\_07`**



**### Provides**



**\* day**

**\* slot**

**\* start/end time**

**\* subject**

**\* faculty**

**\* lecture type**

**\* semester**

**\* academic year**



**### Used for**



**\* Today's classes**

**\* Weekly timetable**

**\* Free-slot detection**

**\* Attendance recovery planning**

**\* Attendance forecast**

**\* future deadline/calendar integration**



**### Join**



**```text**

**subject\_id**

**+**

**semester\_no**

**+**

**academic\_year**

**```**



**---**



**# 2.8 `career\_preferences`**



**### Provides**



**\* preferred domain**

**\* dream role**

**\* preferred industry**

**\* work mode**

**\* target package**

**\* higher studies**

**\* entrepreneurship**

**\* certification interest**

**\* internship completion**

**\* placement readiness**



**### Used for**



**\* Career profile**

**\* Career readiness**

**\* Career gap**

**\* Elective advisor**

**\* Target-role alignment**

**\* Career recommendations**



**The existing intelligence plan explicitly says career guidance should combine Career Preferences + Subject Performance + Semester Summary + Subjects, with deterministic matching before GenAI narrative generation.** 



**---**



**# 2.9 `lifestyle\_survey`**



**### Provides**



**\* sleep**

**\* study hours**

**\* screen time**

**\* physical activity**

**\* stress**

**\* wellbeing**

**\* attendance commitment**

**\* part-time job**

**\* internet access**

**\* learning mode**



**### Used for**



**\*\*Initially:\*\***



**\* private student self-insights**

**\* contextual analytics**



**\*\*Later:\*\***



**\* ML features only where ethically justified.**



**### Critical privacy rule**



**This data must \*\*not automatically appear in Faculty/Admin dashboards\*\*.**



**Especially:**



**```text**

**stress\_level**

**mental\_wellbeing**

**```**



**must remain protected.**



**---**



**# 2.10 `risk\_predictions`**



**### Provides**



**Current:**



**```text**

**prediction\_status**

**prediction\_timestamp**

**created\_at**

**updated\_at**

**```**



**### Used for**



**\* Risk status**

**\* At-risk student indicator**

**\* Explainable risk later**



**### Problem**



**Current table is \*\*not sufficient for auditable ML\*\*.**



**The project status already notes that the ML layer is planned, not live, and current risk rows are placeholder-shaped.** 



**Before real ML:**



**```text**

**model\_version**

**probability**

**feature\_snapshot**

**prediction\_reason**

**prediction\_run\_id**

**```**



**or equivalent auditable storage must be designed.**



**---**



**# 2.11 `faculty\_student\_map`**



**### Provides**



**\* mentor relationship**

**\* faculty/student mapping**

**\* mentor role**

**\* status**

**\* mentor\_since**



**### Used for**



**\* Mentor assignment**

**\* Early-warning loop**

**\* Intervention**

**\* Student support**



**Join:**



**```text**

**faculty\_student\_map.student\_id**

**+**

**faculty\_student\_map.faculty\_id**

**```**



**---**



**# 2.12 `performance\_change\_log`**



**### Used for**



**\* academic change history**

**\* "what changed?"**

**\* marks update notification**

**\* audit transparency**



**Student should have \*\*read-only visibility only where appropriate\*\*.**



**---**



**# 2.13 `attendance\_change\_log`**



**### Used for**



**\* attendance update history**

**\* "what changed?"**

**\* audit evidence**

**\* future dispute/review workflow**



**Again:**



**```text**

**Student → READ**

**Faculty/Admin → authorized WRITE through academic workflow**

**```**



**---**



**# 2.14 `student\_messages`**



**This is especially important for the new Notification system.**



**The live database contains:**



**```text**

**student\_messages**

**```**



**and currently it has \*\*0 rows\*\*.** 



**Before implementation:**



**\*\*inspect its exact columns and existing intended semantics.\*\***



**If it can represent:**



**```text**

**student\_id**

**message**

**type**

**read/unread**

**created\_at**

**```**



**then reuse it.**



**If not, extend it minimally.**



**\*\*Do not immediately create `notifications`, `student\_notifications`, `alerts`, etc.\*\***



**---**



**# 3. Student Dashboard Data Flow**



**Final architecture:**



**```text**

&#x20;                        **STUDENT JWT**

&#x20;                             **│**

&#x20;                             **▼**

&#x20;                        **requireRole**

&#x20;                             **│**

&#x20;                             **▼**

&#x20;                       **Student Service**

&#x20;                             **│**

&#x20;      **┌──────────────────────┼──────────────────────┐**

&#x20;      **▼                      ▼                      ▼**

&#x20;  **students           semester\_summary        subject data**

&#x20;      **│                      │                      │**

&#x20;      **│                      │              ┌───────┴────────┐**

&#x20;      **│                      │              ▼                ▼**

&#x20;      **│                      │        performance         attendance**

&#x20;      **│                      │**

&#x20;      **└──────────────────────┼──────────────────────┘**

&#x20;                             **▼**

&#x20;                    **Student Dashboard DTO**

&#x20;                             **│**

&#x20;                             **▼**

&#x20;                           **BFF**

&#x20;                             **│**

&#x20;                             **▼**

&#x20;                        **Student UI**

**```**



**### Dashboard should NOT call DB directly.**



**Existing architecture explicitly says components receive data through API/BFF, never direct DB calls.** 



**---**



**# 4. Attendance Implementation Plan**



**## Core attendance**



**### Overall**



**Use aggregate `attendance`:**



**```text**

**SUM(attended\_classes)**

**---------------------- × 100**

**SUM(total\_classes)**

**```**



**\*\*Do not average subject percentages.\*\***



**---**



**## Subject attendance**



**```text**

**enrollment**

&#x20;   **+**

**attendance**

&#x20;   **+**

**subjects**

**```**



**Output:**



**```text**

**Subject**

**Present**

**Absent**

**Total**

**Percentage**

**Status**

**Eligibility**

**Shortage**

**```**



**---**



**## Daily history**



**```text**

**daily\_attendance\_07**

&#x20;       **+**

**student\_id**

&#x20;       **+**

**subject\_id**

**```**



**Output:**



**```text**

**Date**

**Subject**

**Lecture**

**Status**

**```**



**---**



**## Attendance calculator**



**Given:**



**```text**

**P = attended**

**T = total**

**target = threshold**

**```**



**For additional classes `x`:**



**```text**

**(P + x)/(T + x) >= target**

**```**



**Solve for minimum `x`.**



**For classes that can be missed:**



**```text**

**P/(T + x) >= target**

**```**



**All calculation in backend/service layer.**



**---**



**## Attendance eligibility**



**Use existing Threshold Engine.**



**Existing validated threshold is 75%, with critical/excellent thresholds also centralized.** 



**Student UI only consumes:**



**```text**

**Eligible**

**At Risk**

**Not Eligible**

**```**



**It does not invent these values.**



**---**



**## Recovery plan**



**Combine:**



**```text**

**attendance**

**+**

**weekly\_timetable\_07**

**+**

**current\_date**

**+**

**eligibility threshold**

**```**



**Output:**



**```text**

**Current: 68%**

**Target: 75%**



**Upcoming relevant classes: 6**

**Required attendance: 5/6**

**Can miss: 1**

**```**



**If timetable doesn't contain enough future sessions:**



**> Recovery within current timetable cannot be guaranteed.**



**Never fabricate future classes.**



**---**



**# 5. Marks Implementation Plan**



**## Source**



**Primary:**



**```text**

**student\_subject\_performance**

**```**



**Joined with:**



**```text**

**student\_subject\_enrollment**

**subjects**

**```**



**---**



**## Subject marks**



**```text**

**Internal**

**Mid-sem**

**End-sem**

**Total**

**Percentage**

**Grade**

**Result**

**Category**

**```**



**---**



**## Component analytics**



**If populated:**



**```text**

**CT1**

**CT2**

**Mid**

**End**

**```**



**Then:**



**```text**

**assessment %**

**↓**

**trend**

**↓**

**component weakness**

**```**



**If NULL:**



**```text**

**Not entered**

**```**



**No zero substitution.**



**---**



**## Marks simulator**



**This is \*\*not a database write\*\*.**



**```text**

**Existing DB values**

&#x20;     **↓**

**Temporary calculation**

&#x20;     **↓**

**Projected result**

**```**



**No persistence.**



**---**



**## Semester-level data**



**Use:**



**```text**

**student\_semester\_summary**

**```**



**for:**



**\* SGPA**

**\* semester percentage**

**\* semester grade**

**\* credits**

**\* backlogs**



**Until ETL refresh is operational, show:**



**> Semester summary last updated …**



**because subject marks may be newer than semester summary. The existing marks plan explicitly identifies this freshness issue.** 



**---**



**# 6. Notification Implementation Plan**



**## Notification sources**



**### Marks**



**```text**

**performance\_change\_log**

**```**



**→ detect meaningful publication/update.**



**### Attendance**



**```text**

**attendance\_change\_log**

**+**

**attendance**

**```**



**→ detect threshold crossing.**



**### Timetable**



**```text**

**weekly\_timetable\_07**

**```**



**→ detect timetable changes.**



**### Risk**



**```text**

**risk\_predictions**

**```**



**→ notification when prediction state changes.**



**---**



**## Example**



**```text**

**Faculty updates End-sem**

&#x20;       **↓**

**student\_subject\_performance**

&#x20;       **↓**

**performance\_change\_log**

&#x20;       **↓**

**notification event**

&#x20;       **↓**

**student\_messages**

&#x20;       **↓**

**Student Notification Center**

**```**



**### Notification types**



**```text**

**MARKS\_PUBLISHED**

**MARKS\_UPDATED**

**ATTENDANCE\_WARNING**

**PERFORMANCE\_CHANGE**

**TIMETABLE\_CHANGE**

**RISK\_ALERT**

**SYSTEM**

**```**



**---**



**## Notification UI**



**```text**

**🔔 Notifications**



**Unread: 3**



**Marks Published**

**Deep Learning End-sem marks are now available.**

**10 min ago**



**Attendance Alert**

**NLP attendance dropped below 75%.**

**1 hour ago**



**Timetable Updated**

**Thursday Deep Learning slot changed.**

**Yesterday**

**```**



**Student can:**



**\* read**

**\* mark read**

**\* filter**



**But cannot modify the underlying academic event.**



**---**



**# 7. Advanced Analytics Plan**



**## Academic Health Score**



**Use deterministic components:**



**```text**

**Attendance**

**+**

**Performance**

**+**

**Academic Progress**

**+**

**Consistency**

**```**



**Server-side.**



**Do not call it ML.**



**---**



**## What Should I Focus On?**



**Rule engine:**



**```text**

**Low attendance**

**OR**

**low performance**

**OR**

**declining trend**

**OR**

**pending assessment**

**OR**

**backlog**

**```**



**Output top 3 priorities.**



**---**



**## Needs Attention**



**Examples:**



**```text**

**NLP attendance < threshold**

**Software Engineering performance < threshold**

**End-sem missing**

**Backlog present**

**```**



**---**



**## Subject comparison**



**```text**

**Student performance**

**vs**

**anonymous cohort average**

**```**



**Never expose another student's:**



**\* name**

**\* marks**

**\* attendance**

**\* rank**



**---**



**## Learning gap**



**Use:**



**```text**

**assessment components**

**+**

**subject performance**

**+**

**historical trend**

**```**



**Example:**



**```text**

**CT1 80%**

**CT2 61%**

**Mid 56%**



**↓**

**Declining assessment performance**

**```**



**Not unsupported psychological diagnosis.**



**---**



**## Strength / weakness**



**Rank subjects based on:**



**```text**

**percentage**

**+**

**trend**

**+**

**attendance**

**```**



**---**



**## Academic goals**



**Student-defined target:**



**```text**

**Target SGPA**

**Target attendance**

**Target percentage**

**```**



**Backend calculates progress.**



**---**



**# 8. Career Intelligence Plan**



**Architecture:**



**```text**

**career\_preferences**

&#x20;       **+**

**student\_subject\_performance**

&#x20;       **+**

**student\_semester\_summary**

&#x20;       **+**

**subjects**

&#x20;       **+**

**optional lifestyle context**

&#x20;       **↓**

**Career Matching Engine**

&#x20;       **↓**

**Career Readiness**

**Career Gaps**

**Recommendations**

**```**



**### Career readiness**



**Structured score.**



**### Career gap**



**```text**

**Target:**

**AI/ML Engineer**



**Academic alignment**

**Skill alignment**

**Experience**

**Certification**

**```**



**### Elective recommendation**



**```text**

**subjects**

**+**

**subject\_type**

**+**

**career preference**

**+**

**performance**

**```**



**Output:**



**```text**

**Recommended**

**Why**

**Evidence**

**Confidence/strength of alignment**

**```**



**The recommendation engine remains deterministic; GenAI only explains it later. This separation is explicitly supported by the existing intelligence architecture.** 



**---**



**# 9. ML Dataset Combinations + Models**



**This is where we \*\*must not rush\*\*.**



**Current project status says ML is planned, not implemented, and ETL is also not yet the production refresh mechanism.** 



**Therefore:**



**```text**

**ETL/Data Quality**

&#x20;     **↓**

**Feature Dataset**

&#x20;     **↓**

**ML**

**```**



**not:**



**```text**

**Current seed tables**

&#x20;     **↓**

**Random ML**

**```**



**---**



**## ML Model A — At-Risk Prediction**



**### Tables**



**```text**

**students**

**+**

**student\_subject\_enrollment**

**+**

**student\_subject\_performance**

**+**

**attendance**

**+**

**student\_semester\_summary**

**+**

**optional lifestyle\_survey**

**+**

**historical outcomes**

**```**



**### Join**



**```text**

**student\_id**

**+**

**enrollment\_record\_id**

**+**

**semester\_no**

**+**

**academic\_year**

**```**



**### Features**



**Academic:**



**\* previous SGPA**

**\* current percentage**

**\* marks trajectory**

**\* backlog count**

**\* credits earned ratio**

**\* subject failures**



**Attendance:**



**\* overall attendance**

**\* subject attendance**

**\* attendance trend**

**\* shortage count**



**Performance:**



**\* CT/Mid/End trends where populated**

**\* grade trajectory**

**\* failed subjects**



**Context:**



**\* study hours**

**\* sleep**

**\* stress**



**Sensitive context should only be included after a clear governance decision.**



**### Target**



**For example:**



**```text**

**at\_risk\_next\_period = 1/0**

**```**



**But the exact target definition must be finalized from historical outcomes.**



**### Model**



**Start with:**



**```text**

**Logistic Regression**

**+**

**XGBoost**

**```**



**Compare.**



**Do not jump to deep learning.**



**---**



**# 10. Performance Prediction**



**### Inputs**



**```text**

**past semester performance**

**+**

**current subject components**

**+**

**attendance**

**+**

**credits**

**+**

**subject history**

**```**



**### Target**



**Potentially:**



**```text**

**next semester percentage**

**```**



**or:**



**```text**

**final subject percentage**

**```**



**depending on available historical labels.**



**### Models**



**\* Linear/ElasticNet baseline**

**\* Random Forest**

**\* XGBoost**



**Select using validation metrics, not preference.**



**---**



**# 11. Trend Prediction**



**Two separate levels:**



**### Student trend**



**```text**

**student\_id**

**+**

**semester\_no**

**+**

**semester\_percentage/SGPA**

**```**



**### Cohort trend**



**```text**

**department**

**+**

**admission cohort**

**+**

**semester**

**```**



**Output:**



**```text**

**historical trend**

**+**

**forecast**

**+**

**uncertainty**

**```**



**Never present forecast as certainty.**



**---**



**# 12. ML Training Strategy**



**Because current data is only around 80 students and 500 semester-summary rows, \*\*we must not pretend this is a large ML dataset\*\*.**



**Plan:**



**```text**

**Historical data**

&#x20;     **↓**

**Student-level leakage-safe split**

&#x20;     **↓**

**Train**

**Validation**

**Test**

**```**



**Prefer temporal validation:**



**```text**

**Past semesters → training**

**Later semester → validation/test**

**```**



**Avoid randomly splitting rows from the same student across train/test because that creates leakage.**



**---**



**# 13. ML Storage**



**Current:**



**```text**

**risk\_predictions**

**```**



**is not enough for a real auditable ML output.**



**Plan to extend/create a proper prediction storage model containing at least:**



**```text**

**prediction\_id**

**student\_id**

**prediction\_type**

**prediction\_status**

**probability**

**model\_version**

**feature\_snapshot\_id**

**prediction\_timestamp**

**prediction\_horizon**

**prediction\_reason**

**```**



**And separately:**



**```text**

**model\_registry**

**```**



**or MLflow as the actual model registry.**



**The existing architecture already anticipates model versioning, SHAP and prediction feedback.** 



**---**



**# 14. SHAP / Explainability**



**For XGBoost:**



**```text**

**prediction**

&#x20;  **↓**

**SHAP**

&#x20;  **↓**

**Top contributing factors**

**```**



**Example:**



**```text**

**Risk: Moderate**



**Main contributing factors:**



**Attendance        ↓**

**Performance       ↓**

**Backlog count     ↓**

**Previous SGPA     ↑ protective**

**```**



**Student UI should translate this into understandable language.**



**No raw SHAP vector exposed to students.**



**---**



**# 15. GenAI Architecture**



**GenAI comes \*\*after verified analytics/ML\*\*.**



**```text**

**Verified DB**

&#x20;    **↓**

**Structured analytics**

&#x20;    **↓**

**ML outputs**

&#x20;    **↓**

**Grounded context object**

&#x20;    **↓**

**GenAI**

&#x20;    **↓**

**Validated response**

&#x20;    **↓**

**Student UI**

**```**



**### AI Academic Coach**



**Can answer:**



**> Why is my attendance risky?**



**But it receives:**



**```text**

**attendance = 68**

**threshold = 75**

**required\_classes = 5**

**```**



**not raw unrestricted DB access.**



**---**



**## GenAI responsibilities**



**Good:**



**\* explain**

**\* summarize**

**\* personalize**

**\* generate study plan**

**\* explain career gap**



**Bad:**



**\* calculate marks**

**\* calculate attendance**

**\* decide eligibility**

**\* invent timetable**

**\* invent career requirements**

**\* override ML output**



**---**



**# 16. API Changes**



**## Existing APIs — preserve**



**```text**

**/me/profile**

**/me/academic-summary**

**/me/performance**

**```**



**No breaking changes.**



**---**



**## New read APIs**



**Likely additions:**



**```text**

**GET /me/dashboard**

**GET /me/attendance**

**GET /me/attendance/history**

**GET /me/attendance/recovery**

**GET /me/timetable**

**GET /me/notifications**

**GET /me/notifications/unread-count**

**GET /me/analytics/health**

**GET /me/analytics/focus**

**GET /me/analytics/learning-gaps**

**GET /me/career**

**GET /me/risk**

**```**



**Exact endpoints should be finalized after inspecting the current API contracts and avoiding redundant endpoints.**



**### Important principle**



**Don't create:**



**```text**

**20 APIs for 20 cards.**

**```**



**Prefer domain-oriented responses.**



**For example:**



**```text**

**GET /me/dashboard**

**```**



**can return:**



**```text**

**identity**

**summary**

**today**

**alerts**

**attendance**

**performance**

**```**



**where appropriate.**



**---**



**# 17. Read-Only Security**



**Backend must derive student identity from authenticated session/token.**



**Not:**



**```text**

**GET /student?student\_id=STU000002**

**```**



**and trust frontend input.**



**Instead:**



**```text**

**Authenticated User**

&#x20;     **↓**

**user.student\_id**

&#x20;     **↓**

**Student Service**

&#x20;     **↓**

**WHERE student\_id = authenticated\_student\_id**

**```**



**### Test cases**



**Student A must not access:**



**```text**

**Student B profile**

**Student B marks**

**Student B attendance**

**Student B career data**

**Student B lifestyle**

**Student B risk**

**```**



**Even if Student A changes URL/query parameters.**



**---**



**# 18. Realtime Strategy**



**There are two levels.**



**## Level 1 — Academic data**



**Faculty:**



**```text**

**Marks/Attendance update**

&#x20;       **↓**

**PostgreSQL**

&#x20;       **↓**

**Student next request/refresh**

&#x20;       **↓**

**BFF cache bypass/revalidation**

&#x20;       **↓**

**fresh data**

**```**



**This is the safest first implementation because current architecture already uses BFF caching.**



**---**



**## Level 2 — True live notifications**



**For notification events:**



**```text**

**Faculty action**

&#x20;     **↓**

**DB audit/event**

&#x20;     **↓**

**student\_messages**

&#x20;     **↓**

**notification subscription**

&#x20;     **↓**

**Student notification badge**

**```**



**Supabase Realtime can be evaluated here, but \*\*not as a replacement for backend authorization\*\*.**



**The browser must never directly bypass the FastAPI/BFF authorization model just because Realtime exists.**



**### Recommended approach**



**```text**

**Academic data:**

**API/BFF authoritative**



**Notifications:**

**Realtime optional enhancement**

**```**



**---**



**# 19. Database Changes Required**



**## No changes required for Phase 1 core**



**Existing tables are enough for:**



**\* profile**

**\* subjects**

**\* attendance**

**\* marks**

**\* semester history**

**\* timetable**

**\* basic career profile**



**---**



**## Likely required later**



**### Notifications**



**Reuse:**



**```text**

**student\_messages**

**```**



**after inspecting exact schema.**



**Only extend if necessary.**



**---**



**### ML**



**Extend/replace current placeholder-shaped prediction storage with auditable ML metadata.**



**---**



**### Student disputes**



**Future:**



**```text**

**attendance\_disputes**

**marks\_recheck\_requests**

**```**



**These are \*\*workflow tables\*\*, not academic source-of-truth tables.**



**---**



**### Assignments**



**If later approved:**



**```text**

**assignments**

**```**



**and potentially:**



**```text**

**assignment\_submissions**

**```**



**---**



**### Consent**



**For Responsible AI:**



**```text**

**student\_data\_consents**

**```**



**or an equivalent structured consent model.**



**Do not hide consent state inside unrelated columns.**



**---**



**# 20. Frontend Components**



**## Reuse existing**



**The project already has:**



**\* `StatCard`**

**\* `ChartCard`**

**\* `SubjectCard`**

**\* `FreshnessBadge`**

**\* `LoadingSkeleton`**

**\* `EmptyState`**

**\* `ErrorState`**

**\* `TrendChart`**

**\* `BarChart`**

**\* `GradeBadge`**

**\* `DataTable`**

**\* `AvatarInitials`**



**The Student plan specifically defines these shared components and says composition/reuse should be preferred.** 



**---**



**## New Student components**



**Potential:**



**```text**

**components/student/**

**├── dashboard/**

**│   ├── academic-health-card**

**│   ├── focus-areas**

**│   ├── todays-classes**

**│   ├── needs-attention**

**│   └── what-changed**

**│**

**├── attendance/**

**│   ├── attendance-overview**

**│   ├── subject-attendance-card**

**│   ├── attendance-calendar**

**│   ├── attendance-calculator**

**│   ├── recovery-plan**

**│   └── eligibility-card**

**│**

**├── academic/**

**│   ├── marks-overview**

**│   ├── assessment-breakdown**

**│   ├── learning-gap**

**│   └── marks-simulator**

**│**

**├── career/**

**│   ├── career-profile**

**│   ├── readiness-score**

**│   └── career-gap**

**│**

**└── notifications/**

&#x20;   **├── notification-list**

&#x20;   **└── notification-badge**

**```**



**But \*\*don't create these blindly\*\*. Before each implementation slice, inspect whether an existing component can be extended.**



**---**



**# 21. UI Rules**



**Existing KenexAI design system stays.**



**```text**

**NO globals.css modification**

**NO new global theme**

**NO unrelated redesign**

**NO duplicate design system**

**NO hardcoded data**

**```**



**The project already targets a TweakCN/Twitter-style responsive system and WCAG 2.1 AA.** 



**---**



**# 22. Caching Strategy**



**Current BFF uses caching.**



**For Student academic data:**



**```text**

**Normal:**

**short TTL**



**After known faculty update:**

**bypass/revalidate**



**Manual refresh:**

**bypass cache**

**```**



**For critical data like:**



**```text**

**eligibility**

**attendance**

**marks**

**```**



**don't allow stale data to be presented as current without a freshness indicator.**



**---**



**# 23. Feature Dependency Graph**



**This is the \*\*actual implementation dependency order\*\* I'd lock.**



**```text**

**PHASE 0**

**Existing API/schema verification**

&#x20;       **↓**

**PHASE 1**

**Student data foundation**

&#x20;       **↓**

**Profile + Subjects + Marks + Attendance**

&#x20;       **↓**

**Timetable**

&#x20;       **↓**

**Freshness/error/loading**

&#x20;       **↓**

**PHASE 2**

**Attendance intelligence**

&#x20;       **↓**

**Eligibility**

**Calculator**

**Recovery**

**Calendar**

&#x20;       **↓**

**PHASE 3**

**Academic analytics**

&#x20;       **↓**

**Health**

**Focus**

**Needs Attention**

**Learning Gaps**

**Trends**

**What-if**

&#x20;       **↓**

**PHASE 4**

**Notifications**

&#x20;       **↓**

**PHASE 5**

**Career intelligence**

&#x20;       **↓**

**PHASE 6**

**ML**

&#x20;       **↓**

**PHASE 7**

**GenAI**

**```**



**---**



**# 24. Exact Data Stitching Matrix**



**This is the core thing you asked for.**



**| Tables                                    | Join Key                  | Feature                | Logic                  | Output                | Storage            | API                    | UI         |**

**| ----------------------------------------- | ------------------------- | ---------------------- | ---------------------- | --------------------- | ------------------ | ---------------------- | ---------- |**

**| `students` + `student\_semester\_summary`   | `student\_id`              | Academic overview      | latest semester        | SGPA/credits/backlogs | existing           | `/me/academic-summary` | Dashboard  |**

**| `students` + `student\_subject\_enrollment` | `student\_id`              | My Subjects            | active/current term    | subject list          | existing           | `/me/performance`      | Subjects   |**

**| Enrollment + Performance                  | `enrollment\_record\_id`    | Marks                  | read canonical marks   | marks/grade           | existing           | performance            | Academic   |**

**| Enrollment + Attendance                   | `enrollment\_record\_id`    | Attendance             | aggregate              | %/eligibility         | existing           | attendance             | Attendance |**

**| Student + Daily Attendance                | `student\_id + subject\_id` | Attendance history     | group/date             | P/A history           | existing           | new read API           | Calendar   |**

**| Attendance + Timetable                    | subject/semester/year     | Recovery               | future sessions        | required classes      | none               | new API                | Recovery   |**

**| Performance components                    | `enrollment\_record\_id`    | Weak areas             | assessment trend       | component weakness    | none               | analytics API          | Subject    |**

**| Semester Summary                          | `student\_id + semester`   | Trend                  | historical sequence    | SGPA trend            | none               | academic               | Academic   |**

**| Semester Summary + cohort                 | cohort + semester         | Cohort trend           | aggregate              | cohort benchmark      | none               | analytics              | Analytics  |**

**| Enrollment + Performance + Subjects       | subject                   | Credit workload        | group by credits       | performance/load      | none               | analytics              | Academic   |**

**| Career + Performance + Subjects           | `student\_id`, subject     | Career readiness       | deterministic matching | alignment             | future output      | career API             | Career     |**

**| Career + Subjects                         | domain/role               | Elective advisor       | career alignment       | recommendations       | none initially     | career API             | Career     |**

**| Risk + student                            | `student\_id`              | Risk                   | ML output              | status/probability    | risk table         | risk API               | Dashboard  |**

**| Risk + Faculty Map                        | `student\_id`              | Mentor loop            | assigned mentor        | intervention signal   | future             | mentor API             | Faculty    |**

**| Performance Change Log + Performance      | `performance\_id`          | Mark notifications     | change detection       | event                 | `student\_messages` | notification API       | Bell       |**

**| Attendance Change Log + Attendance        | student/subject           | Attendance alerts      | threshold crossing     | event                 | `student\_messages` | notification API       | Bell       |**

**| Timetable + previous state                | timetable key             | timetable notification | changed schedule       | event                 | messages           | notification           | Bell       |**



**---**



**# 25. ML Dependency Matrix**



**| Model               | Required tables                               | Target              | Model                           |**

**| ------------------- | --------------------------------------------- | ------------------- | ------------------------------- |**

**| At-risk             | performance + attendance + semester + history | future risk         | Logistic/XGBoost                |**

**| Performance         | historical performance + attendance           | next performance    | Regression/XGBoost              |**

**| Student trend       | semester summaries                            | next SGPA/%         | regression/time-series baseline |**

**| Cohort trend        | semester summaries + cohort                   | cohort future trend | time-series/regression          |**

**| Attendance forecast | daily attendance + timetable                  | future attendance   | baseline statistical → ML later |**



**### Rule**



**If deterministic calculation can answer it:**



**> \*\*Do not use ML.\*\***



**Examples:**



**\* Attendance %**

**\* classes needed**

**\* classes can miss**

**\* total marks**

**\* grade**

**\* eligibility**

**\* SGPA from existing summary**



**These should remain deterministic.**



**---**



**# 26. GenAI Dependency Matrix**



**| GenAI Feature          | Structured input        | ML needed? |**

**| ---------------------- | ----------------------- | ---------- |**

**| Academic Coach         | student metrics + rules | No         |**

**| Explain risk           | risk + SHAP             | Yes        |**

**| Study plan             | focus areas + timetable | No         |**

**| Career explanation     | career matching         | No         |**

**| Academic Q\&A           | verified student data   | No         |**

**| Faculty/mentor summary | Student360 + risk       | Maybe      |**



**GenAI gets \*\*structured verified context\*\*, not unrestricted database access.**



**---**



**# 27. Important Edge Cases**



**### Marks**



**\* End-sem NULL**

**\* CT1/CT2 NULL**

**\* partial marks**

**\* inconsistent legacy derived fields**

**\* failed attempt**

**\* multiple attempts**

**\* no performance row**



**### Attendance**



**\* zero classes**

**\* no daily records**

**\* 100%**

**\* exactly 75%**

**\* just below 75%**

**\* recovery impossible**

**\* no future timetable sessions**

**\* timetable holiday/weekend**

**\* duplicate daily attendance**



**### Semester**



**\* current semester has no summary**

**\* semester summary stale**

**\* student changed department**

**\* no previous semester**



**### Career**



**\* no career preferences**

**\* no dream role**

**\* no internship**

**\* incomplete preferences**



**### Notifications**



**\* duplicate events**

**\* unread count**

**\* already-read notification**

**\* stale notification**

**\* student deactivated**



**### ML**



**\* insufficient historical data**

**\* class imbalance**

**\* missing features**

**\* unseen subject**

**\* data leakage**

**\* model unavailable**

**\* stale prediction**



**### GenAI**



**\* unsupported question**

**\* missing data**

**\* hallucination**

**\* stale context**

**\* model failure**



**---**



**# 28. Security / Privacy Requirements**



**### Student can read:**



**```text**

**Own profile**

**Own marks**

**Own attendance**

**Own semester history**

**Own timetable**

**Own career preferences**

**Own risk result**

**Own notifications**

**```**



**### Student cannot read:**



**```text**

**Other student's data**

**Faculty-only analytics**

**Other students' lifestyle data**

**Other students' risk**

**Other students' career data**

**Internal audit data beyond approved transparency**

**```**



**### Student cannot write:**



**```text**

**marks**

**attendance**

**grades**

**SGPA**

**CGPA**

**semester summary**

**risk prediction**

**```**



**This remains enforced \*\*server-side\*\*, not merely hidden in UI.**



**---**



**# 29. Implementation Order — Final**



**## Slice 0 — Verification**



**Before coding:**



**\* inspect current Student APIs**

**\* inspect current DB schema**

**\* inspect current BFF**

**\* inspect Student components**

**\* inspect current attendance wiring**

**\* inspect notification table**

**\* verify latest live values**

**\* identify stale APIs/cache**



**\*\*No code change.\*\***



**---**



**## Slice 1 — Student Data Foundation**



**\* profile**

**\* current semester**

**\* subjects**

**\* marks**

**\* attendance**

**\* semester summary**

**\* freshness**



**Acceptance:**



**> Every displayed value comes from live DB/API.**



**---**



**## Slice 2 — Attendance**



**\* all subjects**

**\* aggregate**

**\* daily history**

**\* calendar**

**\* eligibility**



**---**



**## Slice 3 — Timetable**



**\* today's classes**

**\* weekly timetable**

**\* subject mapping**



**---**



**## Slice 4 — Attendance Intelligence**



**\* calculator**

**\* recovery plan**

**\* attendance risk**

**\* shortage explanation**



**---**



**## Slice 5 — Academic Intelligence**



**\* academic health**

**\* focus areas**

**\* needs attention**

**\* subject comparison**

**\* learning gaps**

**\* strengths/weaknesses**



**---**



**## Slice 6 — Marks Intelligence**



**\* assessment breakdown**

**\* component trends**

**\* marks simulator**

**\* what-if**



**---**



**## Slice 7 — Notifications**



**\* student\_messages integration**

**\* unread count**

**\* event generation**

**\* history**

**\* refresh/revalidation**



**---**



**## Slice 8 — Career**



**\* career profile**

**\* readiness**

**\* career gaps**

**\* target-role alignment**

**\* elective recommendation**



**---**



**## Slice 9 — ML Foundation**



**Before model:**



**```text**

**ETL/data quality**

**↓**

**feature dataset**

**↓**

**training dataset**

**↓**

**baseline**

**↓**

**evaluation**

**↓**

**registry**

**↓**

**prediction**

**```**



**---**



**## Slice 10 — ML UI**



**Only after verified predictions:**



**\* risk**

**\* probability**

**\* explanation**

**\* trend prediction**

**\* prediction freshness**



**---**



**## Slice 11 — GenAI**



**Finally:**



**```text**

**Analytics**

**+**

**ML**

**+**

**Career engine**

&#x20;       **↓**

**Structured context**

&#x20;       **↓**

**GenAI**

**```**



**---**



**# 30. Phase Acceptance Criteria**



**## Phase 1**



**Must pass:**



**\* Student sees only own data**

**\* all subjects displayed**

**\* marks live**

**\* attendance live**

**\* timetable live**

**\* no academic write endpoint for Student**

**\* NULL handled correctly**

**\* loading/error/empty states**

**\* mobile responsive**

**\* typecheck**

**\* lint**

**\* build**



**---**



**## Phase 2**



**Must pass:**



**\* attendance calculation mathematically correct**

**\* eligibility threshold from config**

**\* recovery plan deterministic**

**\* learning gaps explainable**

**\* no classmate identity leakage**

**\* simulator never writes DB**



**---**



**## Phase 3**



**Must pass:**



**\* career recommendations traceable to preferences/performance**

**\* no generic unsupported recommendation**

**\* missing preferences handled**



**---**



**## Phase 4**



**Must pass:**



**\* no data leakage**

**\* temporal validation**

**\* baseline comparison**

**\* model version stored**

**\* probability stored**

**\* feature snapshot stored**

**\* SHAP explanation available**

**\* prediction timestamp**

**\* model fallback behavior**



**---**



**## Phase 5**



**Must pass:**



**\* GenAI only uses verified context**

**\* unsupported questions handled safely**

**\* no fabricated marks/attendance**

**\* structured outputs remain source of truth**

**\* GenAI output auditable**



**---**



**# 31. Final Student Module Architecture**



**```text**

&#x20;                        **STUDENT**

&#x20;                           **│**

&#x20;                           **▼**

&#x20;                   **Student Command Center**

&#x20;                           **│**

&#x20;       **┌───────────────────┼───────────────────┐**

&#x20;       **▼                   ▼                   ▼**

&#x20;   **ACADEMICS           ATTENDANCE           CAREER**

&#x20;       **│                   │                   │**

&#x20;  **Marks                  Live %            Preferences**

&#x20;  **Trends                 Calendar           Readiness**

&#x20;  **Weak Areas             Eligibility        Gap Analysis**

&#x20;  **What-if                Recovery           Electives**

&#x20;       **│                   │                   │**

&#x20;       **└───────────────────┼───────────────────┘**

&#x20;                           **▼**

&#x20;                    **STUDENT 360**

&#x20;                           **│**

&#x20;           **┌───────────────┼───────────────┐**

&#x20;           **▼               ▼               ▼**

&#x20;       **Analytics           ML            GenAI**

&#x20;           **│               │               │**

&#x20;           **▼               ▼               ▼**

&#x20;      **Focus Areas       Risk/Trend      Explanation**

&#x20;      **Learning Gap      Prediction      Coach**

&#x20;      **Health Score      SHAP            Action Plan**

&#x20;           **│               │               │**

&#x20;           **└───────────────┼───────────────┘**

&#x20;                           **▼**

&#x20;                   **Student Action Center**

&#x20;                           **│**

&#x20;         **┌─────────────────┼─────────────────┐**

&#x20;         **▼                 ▼                 ▼**

&#x20;     **Notifications      Timetable        Support**

&#x20;     **What Changed       Free Slots        Future Requests**

**```**



**## Final recommendation**



**\*\*Is plan ko main lock karunga, lekin implementation immediately ML/GenAI se start nahi hoga.\*\***



**The correct dependency is:**



**\*\*Live Student data correctness → Attendance/Marks → Timetable → Advanced deterministic analytics → Notifications → Career → ETL → ML → GenAI.\*\***



**This is especially important because the current project status says the \*\*analytics layer is live but ETL, ML and GenAI are not yet production implementations\*\*.** 



**And one more thing: the existing Student Module plan was deliberately designed around only the original three Student APIs and no DB changes.  \*\*Our new plan supersedes that limitation\*\*, but it should do so additively: preserve the existing API contracts where possible, extend them only when a real feature requires it, and never create duplicate academic truth.**



**### 🔒 Final locked principles**



**1. \*\*Student academic data = READ ONLY.\*\***

**2. \*\*Supabase = source of truth.\*\***

**3. \*\*FastAPI = business logic + authorization.\*\***

**4. \*\*Next.js/BFF = access + screen shaping.\*\***

**5. \*\*No direct browser → DB.\*\***

**6. \*\*No frontend business calculations for authoritative values.\*\***

**7. \*\*No global CSS changes.\*\***

**8. \*\*No duplicate tables if existing tables can serve.\*\***

**9. \*\*Deterministic logic before ML.\*\***

**10. \*\*ML before GenAI.\*\***

**11. \*\*GenAI never becomes the source of truth.\*\***

**12. \*\*Every prediction must be explainable/auditable.\*\***

**13. \*\*Sensitive lifestyle data gets strict privacy treatment.\*\***

**14. \*\*Every Student API scopes by authenticated student identity.\*\***

**15. \*\*Every phase must pass typecheck + lint + build + live verification.\*\***



**\*\*Ab ye plan implementation-ready hai. Is stage par code nahi chhedna chahiye; pehle isi ko final architecture baseline maan ke next turn me individual implementation slices banayenge.\*\***








