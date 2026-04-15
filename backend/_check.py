from database import get_connection

# Seed the answer bank with common internship application Q&A
ANSWERS = [
    # --- Work Authorization ---
    ("authorized to work in the u", "Yes", "work_auth"),
    ("authorized to work in the united states", "Yes", "work_auth"),
    ("work authorization", "Yes", "work_auth"),
    ("legally authorized", "Yes", "work_auth"),
    ("now or in the future require sponsorship", "Yes", "work_auth"),
    ("now or in the future need sponsorship", "Yes", "work_auth"),
    ("require sponsorship now or in the future", "Yes", "work_auth"),
    ("need sponsorship now or in the future", "Yes", "work_auth"),
    ("require sponsorship", "No", "work_auth"),
    ("require visa sponsorship", "No", "work_auth"),
    ("need sponsorship", "No", "work_auth"),
    ("immigration sponsorship", "No", "work_auth"),
    ("visa status", "OPT", "work_auth"),
    ("employment eligibility", "Yes", "work_auth"),

    # --- Personal Info ---
    ("first name", "Quan", "personal"),
    ("last name", "Pham", "personal"),
    ("full name", "Quan Pham", "personal"),
    ("preferred name", "Quan", "personal"),
    ("phone", "510-599-1822", "personal"),
    ("phone number", "510-599-1822", "personal"),
    ("email", "phamanhquan4068@gmail.com", "personal"),
    ("email address", "phamanhquan4068@gmail.com", "personal"),

    # --- Location ---
    ("city", "Hayward", "location"),
    ("state", "California", "location"),
    ("zip", "94542", "location"),
    ("country", "United States", "location"),
    ("current location", "Hayward, CA", "location"),
    ("willing to relocate", "Yes", "location"),
    ("open to relocation", "Yes", "location"),
    ("preferred location", "San Francisco Bay Area", "location"),
    ("preferred work location", "San Francisco Bay Area", "location"),
    ("location preference", "San Francisco Bay Area, open to relocation anywhere in the US", "location"),
    ("what location", "San Francisco Bay Area", "location"),
    ("where would you like to work", "San Francisco Bay Area, but open to relocating anywhere in the US", "location"),
    ("work location", "San Francisco Bay Area", "location"),
    ("relocation", "Yes", "location"),
    ("willing to travel", "Yes", "location"),
    ("travel", "Yes", "location"),
    ("travel requirement", "Yes, 25-50%", "location"),
    ("percentage of travel", "25-50%", "location"),
    ("open to travel", "Yes", "location"),
    ("comfortable commuting", "Yes", "location"),
    ("work on-site", "Yes", "location"),
    ("work in office", "Yes", "location"),
    ("remote or in-person", "Open to both", "location"),
    ("hybrid", "Yes", "location"),

    # --- Education ---
    ("university", "California State University, East Bay", "education"),
    ("school", "California State University, East Bay", "education"),
    ("college", "California State University, East Bay", "education"),
    ("degree", "Bachelor of Science", "education"),
    ("major", "Computer Science", "education"),
    ("field of study", "Computer Science", "education"),
    ("graduation", "May 2026", "education"),
    ("expected graduation", "May 2026", "education"),
    ("graduation date", "2026-05", "education"),
    ("graduation year", "2026", "education"),
    ("gpa", "3.62", "education"),
    ("cumulative gpa", "3.62", "education"),
    ("education level", "Bachelor's", "education"),
    ("highest degree", "Bachelor's", "education"),
    ("year in school", "Senior", "education"),
    ("class year", "2026", "education"),
    ("currently enrolled", "Yes", "education"),
    ("currently pursuing", "Yes", "education"),

    # --- Availability / Start Date ---
    ("start date", "June 2026", "availability"),
    ("earliest start", "June 2026", "availability"),
    ("when can you start", "June 2026", "availability"),
    ("available to start", "June 2026", "availability"),
    ("available start date", "2026-06-01", "availability"),
    ("end date", "September 2026", "availability"),
    ("internship duration", "12 weeks", "availability"),
    ("how many hours", "40", "availability"),

    # --- Online Presence ---
    ("linkedin", "", "links"),
    ("github", "https://github.com/PhamAnhQuannn", "links"),
    ("portfolio", "", "links"),
    ("website", "", "links"),
    ("personal website", "", "links"),

    # --- Skills / Experience ---
    ("years of experience", "1", "experience"),
    ("programming languages", "Java, Python, JavaScript, TypeScript, C++", "experience"),
    ("languages you know", "Java, Python, JavaScript, TypeScript, C++", "experience"),
    ("technical skills", "Java, Python, JavaScript, TypeScript, React, Spring Boot, SQL, Docker, Git", "experience"),
    ("frameworks", "React, Next.js, Spring Boot, FastAPI, Django", "experience"),

    # --- Diversity & Demographics (optional, can decline) ---
    ("gender", "Male", "demographics"),
    ("race", "Asian", "demographics"),
    ("ethnicity", "Vietnamese", "demographics"),
    ("veteran", "No", "demographics"),
    ("disability", "No", "demographics"),
    ("pronouns", "He/Him", "demographics"),

    # --- General / Misc ---
    ("how did you hear", "Job board - Handshake", "misc"),
    ("where did you hear", "Job board - Handshake", "misc"),
    ("referral", "No", "misc"),
    ("referred by", "", "misc"),
    ("salary expectation", "I am primarily looking for growth and learning experience. Based on the posted range, I am open for discussion.", "misc"),
    ("compensation expectation", "I am primarily looking for growth and learning experience. Based on the posted range, I am open for discussion.", "misc"),
    ("cover letter", "", "misc"),
    ("additional information", "", "misc"),
    ("anything else", "", "misc"),

    # --- Common Yes/No ---
    ("18 years", "Yes", "eligibility"),
    ("at least 18", "Yes", "eligibility"),
    ("background check", "Yes", "eligibility"),
    ("agree to", "Yes", "eligibility"),
    ("consent", "Yes", "eligibility"),

    # --- Work Authorization Details ---
    ("ead", "EAD valid 06/10/2026 - 06/11/2027", "work_auth"),
    ("work permit", "OPT EAD valid 06/10/2026 - 06/11/2027", "work_auth"),
    ("opt", "OPT EAD start 06/10/2026, end 06/11/2027. Will need STEM OPT or H-1B after.", "work_auth"),
    ("type of work authorization", "OPT (Optional Practical Training)", "work_auth"),
    ("sponsorship in the future", "Yes", "work_auth"),
    ("future sponsorship", "Yes", "work_auth"),
    ("h-1b", "Will need STEM OPT extension or H-1B sponsorship after 06/11/2027", "work_auth"),
    ("employment authorization expiration", "06/11/2027", "work_auth"),
    ("authorization expiration", "06/11/2027", "work_auth"),

    # --- School Details ---
    ("school address", "25800 Carlos Bee Blvd, Hayward, CA 94542", "education"),
    ("university address", "25800 Carlos Bee Blvd, Hayward, CA 94542", "education"),
    ("campus", "California State University, East Bay - Hayward Campus", "education"),
    ("school city", "Hayward", "education"),
    ("school state", "California", "education"),
    ("school zip", "94542", "education"),
    ("dean's list", "Yes", "education"),
    ("honors", "Dean's List (all semesters)", "education"),
    ("academic standing", "Good Standing", "education"),
    ("relevant coursework", "Data Structures & Algorithms, Analysis of Algorithms, Database Architecture, Computer Networks, Operating Systems, Software Engineering, Natural Language Processing, Automata and Computation", "education"),
    ("courses", "Data Structures & Algorithms, Analysis of Algorithms, Database Architecture, Computer Networks, Operating Systems, Software Engineering, NLP", "education"),

    # --- Work Experience ---
    ("current employer", "College of Alameda", "work"),
    ("employer", "College of Alameda", "work"),
    ("employer address", "555 Ralph Appezzato Memorial Pkwy, Alameda, CA 94501", "work"),
    ("work address", "555 Ralph Appezzato Memorial Pkwy, Alameda, CA 94501", "work"),
    ("job title", "IT Support Specialist & Programming Tutor", "work"),
    ("current role", "IT Support Specialist & Programming Tutor", "work"),
    ("current position", "IT Support Specialist & Programming Tutor at College of Alameda", "work"),
    ("employment start", "August 2023", "work"),
    ("how long at current", "Since August 2023", "work"),
    ("supervisor", "", "work"),
    ("may we contact", "Yes", "work"),
    ("reason for leaving", "Graduating and seeking full-time opportunity", "work"),
    ("describe your current role", "Tutor college students in JavaScript, C++, and Python. Troubleshoot hardware/software issues under a senior SWE's mentorship and maintain school applications.", "work"),

    # --- Projects ---
    ("project", "VOCO Real-Time Emergency Dispatch Dashboard: Built a voice-first emergency dashboard using TypeScript, Next.js, Node.js, Socket.IO, Mapbox, and Redis. Mentored by a senior Google SWE. E-Commercia: Full-stack multi-service platform using Java, Spring Boot, React, Next.js, Django, PostgreSQL, MongoDB, Redis, Docker, and Terraform.", "projects"),
    ("describe a project", "VOCO Real-Time Emergency Dispatch Dashboard - Collaborated in a team of 2 to build a voice-first emergency dashboard that processes calls and displays incidents on a live map using TypeScript with Next.js, Node.js, Socket.IO, Mapbox, and Redis. Mentored by a senior Google SWE to apply production practices (Git workflows, CI/CD, deployment on Vercel and AWS Lightsail). Applied Google Gemini, Perplexity API, and ElevenLabs for voice AI.", "projects"),
    ("personal project", "E-Commercia - Full-Stack Multi-Service Platform: Built a Vietnamese-focused e-commerce, jobs, and social platform using Java, TypeScript, Next.js, React, Tailwind, Zustand, Socket.IO. Developed services with Node.js (NestJS/Express), Python (Django REST), and Java (Spring Boot). Integrated PostgreSQL, MongoDB, Redis with Docker, Terraform, and Prometheus/Grafana.", "projects"),
    ("technical project", "VOCO: Real-time emergency dispatch dashboard with voice AI (TypeScript, Next.js, Node.js, Socket.IO, Redis, Mapbox, Google Gemini). E-Commercia: Full-stack e-commerce platform (Java Spring Boot, React, Django, PostgreSQL, MongoDB, Docker, Terraform).", "projects"),

    # --- Additional Info ---
    ("additional information", "Authorized to work in the US under OPT (EAD valid 06/10/2026 - 06/11/2027). Dean's List all semesters at CSUEB. Cumulative GPA: 3.62. Experienced in full-stack development with Java Spring Boot, TypeScript/React, Python Django, and cloud infrastructure (Docker, AWS, Terraform).", "misc"),
    ("anything else", "I am authorized to work in the United States under OPT with no sponsorship required for the internship period. My EAD is valid from 06/10/2026 to 06/11/2027.", "misc"),
    ("why are you interested", "I am passionate about software engineering and eager to apply my skills in Java, Python, TypeScript, and full-stack development in a professional environment. My project experience with real-time systems and multi-service platforms has prepared me to contribute meaningfully to your team.", "misc"),
    ("why should we hire", "I bring strong full-stack skills across Java Spring Boot, TypeScript/React, and Python Django, with hands-on experience building production-grade applications. I was mentored by a senior Google SWE and have consistently earned Dean's List honors with a 3.62 GPA in Computer Science.", "misc"),
    ("strengths", "Full-stack development, quick learner, strong foundation in data structures and algorithms, experience with production practices (CI/CD, Docker, Git workflows), collaborative team player", "misc"),
]

conn = get_connection()

# Clear existing answers to avoid duplicates
conn.execute("DELETE FROM answer_bank")
conn.commit()

# Insert all answers
for pattern, answer, category in ANSWERS:
    conn.execute(
        "INSERT INTO answer_bank (question_pattern, answer, category) VALUES (?, ?, ?)",
        (pattern, answer, category),
    )
conn.commit()

total = conn.execute("SELECT count(*) FROM answer_bank").fetchone()[0]
print(f"Seeded {total} answers")

# Show by category
for row in conn.execute(
    "SELECT category, count(*) as cnt FROM answer_bank GROUP BY category ORDER BY category"
).fetchall():
    print(f"  {row['category']}: {row['cnt']}")

conn.close()
