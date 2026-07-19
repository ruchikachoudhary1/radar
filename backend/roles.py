"""
Curated domain knowledge for RADAR.

These keyword banks and verb lists are the hand-authored "rubric data" behind
the scoring engine. They are intentionally opinionated and editable — treat this
file as the knowledge base you tune for your own target roles.
"""

# Role -> weighted skill/keyword bank.
# Keywords are lowercase. Multi-word phrases are matched as substrings.
ROLE_KEYWORDS = {
    "Software Engineer": [
        "python", "java", "c++", "javascript", "data structures", "algorithms",
        "object-oriented", "rest api", "sql", "git", "docker", "linux",
        "unit testing", "microservices", "system design", "agile", "ci/cd",
        "problem solving", "debugging", "cloud",
    ],
    "Full Stack Developer": [
        "react", "node", "express", "javascript", "typescript", "rest api",
        "graphql", "postgresql", "mongodb", "redis", "docker", "kubernetes",
        "aws", "ci/cd", "git", "html", "css", "tailwind", "next.js", "fastapi",
        "microservices", "authentication", "jwt", "testing", "webpack",
    ],
    "Frontend Developer": [
        "react", "vue", "angular", "javascript", "typescript", "html", "css",
        "tailwind", "sass", "redux", "next.js", "vite", "webpack", "accessibility",
        "responsive design", "figma", "rest api", "graphql", "jest", "storybook",
    ],
    "Backend Developer": [
        "python", "java", "go", "node", "express", "fastapi", "django", "spring",
        "rest api", "graphql", "postgresql", "mysql", "mongodb", "redis", "kafka",
        "docker", "kubernetes", "microservices", "aws", "ci/cd", "unit testing",
    ],
    "Mobile App Developer": [
        "android", "ios", "kotlin", "swift", "react native", "flutter", "dart",
        "java", "rest api", "firebase", "sqlite", "mvvm", "jetpack", "xcode",
        "android studio", "push notifications", "app store", "play store",
        "material design", "git",
    ],
    "Android Developer": [
        "android", "kotlin", "java", "jetpack compose", "mvvm", "room", "retrofit",
        "coroutines", "android studio", "firebase", "sqlite", "material design",
        "rest api", "dagger", "hilt", "gradle", "play store", "unit testing", "git",
    ],
    "iOS Developer": [
        "ios", "swift", "swiftui", "objective-c", "xcode", "uikit", "core data",
        "combine", "mvvm", "rest api", "cocoapods", "firebase", "app store",
        "auto layout", "grand central dispatch", "unit testing", "git", "avfoundation",
    ],
    "Data Scientist": [
        "python", "pandas", "numpy", "scikit-learn", "tensorflow", "pytorch",
        "machine learning", "deep learning", "sql", "statistics", "data visualization",
        "nlp", "matplotlib", "seaborn", "jupyter", "feature engineering",
        "regression", "classification", "a/b testing", "spark",
    ],
    "Data Analyst": [
        "sql", "excel", "python", "pandas", "power bi", "tableau", "data visualization",
        "statistics", "dashboards", "data cleaning", "etl", "reporting",
        "google analytics", "a/b testing", "storytelling", "kpi", "regression",
        "hypothesis testing", "numpy",
    ],
    "Data Engineer": [
        "python", "sql", "spark", "hadoop", "kafka", "airflow", "etl", "data pipeline",
        "snowflake", "redshift", "bigquery", "dbt", "aws", "docker", "kubernetes",
        "data warehouse", "scala", "streaming", "nosql", "terraform",
    ],
    "Machine Learning Engineer": [
        "python", "pytorch", "tensorflow", "scikit-learn", "machine learning",
        "deep learning", "mlops", "docker", "kubernetes", "aws", "model deployment",
        "feature engineering", "nlp", "computer vision", "sql", "airflow",
        "data pipeline", "hugging face", "transformers", "ci/cd",
    ],
    "AI Engineer": [
        "python", "llm", "large language models", "prompt engineering", "rag",
        "langchain", "openai", "hugging face", "transformers", "vector database",
        "embeddings", "pytorch", "nlp", "fine-tuning", "generative ai", "api",
        "fastapi", "docker", "model deployment", "pinecone",
    ],
    "DevOps Engineer": [
        "docker", "kubernetes", "terraform", "ansible", "aws", "azure", "gcp",
        "ci/cd", "jenkins", "github actions", "prometheus", "grafana", "linux",
        "bash", "python", "monitoring", "helm", "nginx", "networking", "iac",
    ],
    "Cloud Engineer": [
        "aws", "azure", "gcp", "terraform", "kubernetes", "docker", "ec2", "s3",
        "lambda", "cloudformation", "iam", "vpc", "ci/cd", "linux", "networking",
        "serverless", "monitoring", "python", "bash", "cost optimization",
    ],
    "Cybersecurity Analyst": [
        "network security", "penetration testing", "siem", "firewall", "vulnerability",
        "incident response", "encryption", "linux", "python", "owasp", "nmap",
        "wireshark", "threat analysis", "risk assessment", "ids", "soc",
        "security auditing", "kali linux", "compliance", "malware analysis",
    ],
    "QA / Test Engineer": [
        "test automation", "selenium", "cypress", "junit", "test cases", "manual testing",
        "api testing", "postman", "jira", "regression testing", "playwright",
        "ci/cd", "bug tracking", "python", "java", "agile", "performance testing",
        "test plan", "sql",
    ],
    "UI/UX Designer": [
        "figma", "adobe xd", "sketch", "wireframing", "prototyping", "user research",
        "usability testing", "design systems", "interaction design", "accessibility",
        "responsive design", "user flows", "information architecture", "personas",
        "visual design", "typography", "html", "css", "invision",
    ],
    "Product Manager": [
        "product strategy", "roadmap", "user research", "agile", "scrum", "stakeholder",
        "prioritization", "a/b testing", "analytics", "wireframing", "kpi",
        "market research", "user stories", "backlog", "go-to-market", "jira",
        "sql", "product lifecycle", "customer feedback",
    ],
    "Business Analyst": [
        "requirements gathering", "sql", "excel", "data analysis", "stakeholder",
        "process mapping", "power bi", "tableau", "user stories", "documentation",
        "agile", "gap analysis", "business process", "jira", "reporting",
        "uml", "kpi", "problem solving", "communication",
    ],
    "Game Developer": [
        "unity", "unreal engine", "c++", "c#", "game design", "3d graphics",
        "physics", "opengl", "directx", "shaders", "animation", "gameplay programming",
        "blender", "multiplayer", "optimization", "ai", "level design", "git", "vr",
    ],
    "Blockchain Developer": [
        "solidity", "ethereum", "smart contracts", "web3", "blockchain", "hardhat",
        "truffle", "defi", "nft", "cryptography", "javascript", "rust", "ipfs",
        "consensus", "metamask", "erc-20", "erc-721", "node", "dapp", "wallet",
    ],
}

# Strong, results-oriented action verbs (a small curated set).
STRONG_ACTION_VERBS = {
    "architected", "built", "designed", "developed", "engineered", "implemented",
    "launched", "led", "optimized", "automated", "reduced", "increased", "improved",
    "scaled", "shipped", "delivered", "created", "migrated", "refactored", "deployed",
    "spearheaded", "streamlined", "accelerated", "boosted", "cut", "drove", "grew",
    "orchestrated", "pioneered", "resolved", "transformed", "achieved", "generated",
}

# Weak / passive openers that dilute impact.
WEAK_PHRASES = {
    "worked on", "responsible for", "helped", "assisted", "involved in",
    "participated in", "was tasked with", "duties included", "handled", "dealt with",
    "in charge of", "familiar with", "exposure to", "worked with",
}

# Sections a strong resume is expected to contain (aliases per canonical section).
EXPECTED_SECTIONS = {
    "contact": ["email", "phone", "@"],
    "education": ["education", "university", "college", "b.tech", "bachelor", "degree"],
    "experience": ["experience", "internship", "employment", "work history"],
    "skills": ["skills", "technologies", "tech stack", "technical skills"],
    "projects": ["projects", "portfolio"],
}
