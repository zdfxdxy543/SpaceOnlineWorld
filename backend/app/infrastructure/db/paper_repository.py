from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from itertools import count

from app.infrastructure.db.session import DatabaseSessionManager
from app.repositories.paper_repository import (
    AbstractPaperRepository,
    CategorySummary,
    PaperDetail,
    PaperDraft,
    PaperStats,
    PaperSummary,
)


class SQLitePaperRepository(AbstractPaperRepository):
    def __init__(self, session_manager: DatabaseSessionManager) -> None:
        self.session_manager = session_manager
        self._paper_counter = count(10000)
        self._draft_counter = count(1)

    def initialize(self) -> None:
        self._create_tables()
        self._seed_if_empty()
        self._sync_counters()

    def _create_tables(self) -> None:
        with self.session_manager.connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS academic_papers (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    authors TEXT NOT NULL,
                    institution TEXT NOT NULL,
                    journal TEXT NOT NULL,
                    publish_date TEXT NOT NULL,
                    keywords TEXT NOT NULL,
                    abstract TEXT NOT NULL,
                    downloads INTEGER DEFAULT 0,
                    pages INTEGER NOT NULL,
                    file_name TEXT NOT NULL,
                    file_size INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS academic_paper_drafts (
                    draft_id TEXT PRIMARY KEY,
                    paper_id TEXT NOT NULL,
                    requested_title TEXT NOT NULL,
                    requested_authors TEXT NOT NULL,
                    requested_institution TEXT NOT NULL,
                    requested_journal TEXT NOT NULL,
                    requested_publish_date TEXT NOT NULL,
                    requested_keywords TEXT NOT NULL,
                    requested_abstract TEXT NOT NULL,
                    requested_pages INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS academic_categories (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    display_order INTEGER DEFAULT 0
                )
            """)
            conn.commit()

    def _seed_if_empty(self) -> None:
        with self.session_manager.connect() as conn:
            count_row = conn.execute("SELECT COUNT(1) as cnt FROM academic_papers").fetchone()
            if count_row["cnt"] > 0:
                return

            categories = [
                ("computer", "Computer Science", 1),
                ("medicine", "Medicine", 2),
                ("economics", "Economics", 3),
                ("education", "Education", 4),
                ("engineering", "Engineering", 5),
                ("law", "Law", 6),
            ]
            for cat_id, name, order in categories:
                conn.execute(
                    "INSERT OR IGNORE INTO academic_categories (id, name, display_order) VALUES (?, ?, ?)",
                    (cat_id, name, order),
                )

            sample_papers = [
                {
                    "title": "Deep Learning Based Natural Language Processing Research",
                    "authors": json.dumps(["Zhang San", "Li Si"]),
                    "institution": "Tsinghua University",
                    "journal": "Journal of Computers",
                    "publish_date": "2000-03-15",
                    "keywords": json.dumps(["Deep Learning", "Natural Language Processing", "Recurrent Neural Network", "Text Classification"]),
                    "abstract": "This paper proposes a deep learning based natural language processing method that improves text classification accuracy by modifying the structure of recurrent neural networks. Experimental results show that the method achieves significant performance improvements on multiple benchmark datasets.",
                    "downloads": 1523,
                    "pages": 12,
                    "file_name": "zhangsan_nlp_2000.pdf",
                    "file_size": 2048576,
                },
                {
                    "title": "E-commerce Website User Experience Optimization Strategy Research",
                    "authors": json.dumps(["Wang Wu", "Liu Liu"]),
                    "institution": "Peking University",
                    "journal": "Journal of Information Systems",
                    "publish_date": "1999-08-20",
                    "keywords": json.dumps(["E-commerce", "User Experience", "Website Optimization", "Human-Computer Interaction"]),
                    "abstract": "With the rapid development of the Internet, user experience on e-commerce websites has become increasingly important. Through analysis of existing e-commerce websites, this paper proposes a series of user experience optimization strategies.",
                    "downloads": 892,
                    "pages": 8,
                    "file_name": "wangwu_ecommerce_1999.pdf",
                    "file_size": 1536000,
                },
                {
                    "title": "Design and Implementation of Distributed Database Systems",
                    "authors": json.dumps(["Zhou Qi", "Wu Ba", "Zheng Jiu"]),
                    "institution": "Shanghai Jiao Tong University",
                    "journal": "Journal of Software",
                    "publish_date": "1999-11-10",
                    "keywords": json.dumps(["Distributed Database", "Data Sharding", "Load Balancing", "Fault Recovery"]),
                    "abstract": "This paper introduces the design and implementation of a new distributed database system. The system adopts a three-tier architecture and supports features such as data sharding, load balancing, and fault recovery.",
                    "downloads": 2341,
                    "pages": 15,
                    "file_name": "liu_distributed_1999.pdf",
                    "file_size": 3145728,
                },
                {
                    "title": "Application of Artificial Intelligence in Medical Imaging Diagnosis",
                    "authors": json.dumps(["Sun Shi", "Wu Shiyi"]),
                    "institution": "Zhejiang University",
                    "journal": "Computer Application Research",
                    "publish_date": "2000-01-05",
                    "keywords": json.dumps(["Artificial Intelligence", "Medical Imaging", "Convolutional Neural Network", "Computer-Aided Diagnosis"]),
                    "abstract": "Medical imaging diagnosis is one of the important application areas of artificial intelligence technology. This paper proposes a convolutional neural network based medical image classification method.",
                    "downloads": 3102,
                    "pages": 10,
                    "file_name": "sun_medical_2000.pdf",
                    "file_size": 2621440,
                },
                {
                    "title": "Network Security Firewall Technology Research",
                    "authors": json.dumps(["Zheng Shier"]),
                    "institution": "University of Science and Technology of China",
                    "journal": "Computer Engineering",
                    "publish_date": "1998-06-18",
                    "keywords": json.dumps(["Network Security", "Firewall", "State Inspection", "Intrusion Detection"]),
                    "abstract": "Firewall is the first line of defense in network security. This paper analyzes in detail the advantages and disadvantages of existing firewall technology and proposes an improved firewall scheme based on state inspection.",
                    "downloads": 1876,
                    "pages": 9,
                    "file_name": "zheng_firewall_1998.pdf",
                    "file_size": 1843200,
                },
                {
                    "title": "Web Data Mining Technology and Its Applications",
                    "authors": json.dumps(["Qian Shisan", "Feng Shisi"]),
                    "institution": "Fudan University",
                    "journal": "Data Mining and Knowledge Discovery",
                    "publish_date": "1999-04-22",
                    "keywords": json.dumps(["Data Mining", "Web Mining", "Information Retrieval", "Knowledge Discovery"]),
                    "abstract": "With the popularization of the World Wide Web, Web data mining has become a hot research direction in the field of information processing. This paper discusses Web log mining, page structure mining and Web content mining technologies.",
                    "downloads": 1456,
                    "pages": 11,
                    "file_name": "qian_webmining_1999.pdf",
                    "file_size": 2359296,
                },
            ]

            now = datetime.now(timezone.utc).isoformat()
            for paper_data in sample_papers:
                paper_id = f"p{next(self._paper_counter)}"
                conn.execute(
                    """
                    INSERT INTO academic_papers (
                        id, title, authors, institution, journal, publish_date,
                        keywords, abstract, downloads, pages, file_name, file_size,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        paper_id,
                        paper_data["title"],
                        paper_data["authors"],
                        paper_data["institution"],
                        paper_data["journal"],
                        paper_data["publish_date"],
                        paper_data["keywords"],
                        paper_data["abstract"],
                        paper_data["downloads"],
                        paper_data["pages"],
                        paper_data["file_name"],
                        paper_data["file_size"],
                        now,
                        now,
                    ),
                )
            conn.commit()

    def _sync_counters(self) -> None:
        with self.session_manager.connect() as conn:
            max_id = conn.execute("SELECT MAX(CAST(SUBSTR(id, 2) AS INTEGER)) as max_id FROM academic_papers").fetchone()
            if max_id["max_id"]:
                self._paper_counter = count(max_id["max_id"] + 1)

            draft_max_id = conn.execute("SELECT MAX(CAST(SUBSTR(draft_id, 2) AS INTEGER)) as max_id FROM academic_paper_drafts").fetchone()
            if draft_max_id["max_id"]:
                self._draft_counter = count(draft_max_id["max_id"] + 1)

    def _map_paper_summary(self, row: sqlite3.Row) -> PaperSummary:
        return PaperSummary(
            paper_id=row["id"],
            title=row["title"],
            authors=json.loads(row["authors"]),
            institution=row["institution"],
            journal=row["journal"],
            publish_date=row["publish_date"],
            keywords=json.loads(row["keywords"]),
            downloads=row["downloads"],
            pages=row["pages"],
            file_size=row["file_size"],
            file_name=row["file_name"],
        )

    def get_stats(self) -> PaperStats:
        with self.session_manager.connect() as conn:
            paper_count = conn.execute("SELECT COUNT(1) as cnt FROM academic_papers").fetchone()["cnt"]
            journal_count = conn.execute("SELECT COUNT(DISTINCT journal) as cnt FROM academic_papers").fetchone()["cnt"]

        return PaperStats(
            total_papers=paper_count,
            total_journals=journal_count,
        )

    def list_categories(self) -> list[CategorySummary]:
        with self.session_manager.connect() as conn:
            rows = conn.execute(
                """
                SELECT c.id, c.name, COUNT(p.id) as paper_count
                FROM academic_categories c
                LEFT JOIN academic_papers p ON 1=1
                GROUP BY c.id, c.name
                ORDER BY c.display_order ASC
                """
            ).fetchall()

        return [
            CategorySummary(
                id=row["id"],
                name=row["name"],
                paper_count=row["paper_count"],
            )
            for row in rows
        ]

    def list_papers(self, category: str | None = None, limit: int = 20) -> list[PaperSummary]:
        with self.session_manager.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, title, authors, institution, journal, publish_date,
                       keywords, downloads, pages, file_name, file_size
                FROM academic_papers
                ORDER BY publish_date DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()

        return [self._map_paper_summary(row) for row in rows]

    def get_paper(self, paper_id: str) -> PaperDetail | None:
        with self.session_manager.connect() as conn:
            row = conn.execute(
                """
                SELECT id, title, authors, institution, journal, publish_date,
                       keywords, abstract, downloads, pages, file_name, file_size
                FROM academic_papers
                WHERE id = ?
                """,
                (paper_id,),
            ).fetchone()

        if row is None:
            return None

        summary = self._map_paper_summary(row)
        return PaperDetail(
            paper_id=summary.paper_id,
            title=summary.title,
            authors=summary.authors,
            institution=summary.institution,
            journal=summary.journal,
            publish_date=summary.publish_date,
            keywords=summary.keywords,
            downloads=summary.downloads,
            pages=summary.pages,
            file_size=summary.file_size,
            file_name=summary.file_name,
            abstract=row["abstract"],
        )

    def get_hot_papers(self, limit: int = 5) -> list[PaperSummary]:
        with self.session_manager.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, title, authors, institution, journal, publish_date,
                       keywords, downloads, pages, file_name, file_size
                FROM academic_papers
                ORDER BY downloads DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()

        return [self._map_paper_summary(row) for row in rows]

    def search_papers(
        self,
        query: str | None = None,
        field: str | None = None,
        category: str | None = None,
        year_start: int | None = None,
        year_end: int | None = None,
    ) -> list[PaperSummary]:
        sql = """
            SELECT id, title, authors, institution, journal, publish_date,
                   keywords, downloads, pages, file_name, file_size
            FROM academic_papers
            WHERE 1=1
        """
        params = []

        if query and field:
            if field == "title":
                sql += " AND title LIKE ?"
                params.append(f"%{query}%")
            elif field == "author":
                sql += " AND authors LIKE ?"
                params.append(f"%{query}%")
            elif field == "keyword":
                sql += " AND keywords LIKE ?"
                params.append(f"%{query}%")
            elif field == "abstract":
                sql += " AND abstract LIKE ?"
                params.append(f"%{query}%")

        if year_start:
            sql += " AND CAST(SUBSTR(publish_date, 1, 4) AS INTEGER) >= ?"
            params.append(year_start)

        if year_end:
            sql += " AND CAST(SUBSTR(publish_date, 1, 4) AS INTEGER) <= ?"
            params.append(year_end)

        sql += " ORDER BY publish_date DESC"

        with self.session_manager.connect() as conn:
            rows = conn.execute(sql, params).fetchall()

        return [self._map_paper_summary(row) for row in rows]

    def create_paper(
        self,
        *,
        title: str,
        authors: list[str],
        institution: str,
        journal: str,
        publish_date: str,
        keywords: list[str],
        abstract: str,
        pages: int,
        file_name: str,
        file_size: int,
    ) -> PaperDetail:
        paper_id = f"p{next(self._paper_counter)}"
        now = datetime.now(timezone.utc).isoformat()

        with self.session_manager.connect() as conn:
            conn.execute(
                """
                INSERT INTO academic_papers (
                    id, title, authors, institution, journal, publish_date,
                    keywords, abstract, downloads, pages, file_name, file_size,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    paper_id,
                    title,
                    json.dumps(authors),
                    institution,
                    journal,
                    publish_date,
                    json.dumps(keywords),
                    abstract,
                    0,
                    pages,
                    file_name,
                    file_size,
                    now,
                    now,
                ),
            )
            conn.commit()

        return PaperDetail(
            paper_id=paper_id,
            title=title,
            authors=authors,
            institution=institution,
            journal=journal,
            publish_date=publish_date,
            keywords=keywords,
            downloads=0,
            pages=pages,
            file_size=file_size,
            file_name=file_name,
            abstract=abstract,
        )

    def increment_downloads(self, paper_id: str) -> bool:
        with self.session_manager.connect() as conn:
            cursor = conn.execute(
                "UPDATE academic_papers SET downloads = downloads + 1 WHERE id = ?",
                (paper_id,),
            )
            conn.commit()
            return cursor.rowcount > 0

    def create_paper_draft(
        self,
        *,
        requested_title: str,
        requested_authors: list[str],
        requested_institution: str,
        requested_journal: str,
        requested_publish_date: str,
        requested_keywords: list[str],
        requested_abstract: str,
        requested_pages: int,
    ) -> PaperDraft:
        draft_id = f"d{next(self._draft_counter)}"
        paper_id = f"p{next(self._paper_counter)}"
        now = datetime.now(timezone.utc).isoformat()

        with self.session_manager.connect() as conn:
            conn.execute(
                """
                INSERT INTO academic_paper_drafts (
                    draft_id, paper_id, requested_title, requested_authors,
                    requested_institution, requested_journal, requested_publish_date,
                    requested_keywords, requested_abstract, requested_pages, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    draft_id,
                    paper_id,
                    requested_title,
                    json.dumps(requested_authors),
                    requested_institution,
                    requested_journal,
                    requested_publish_date,
                    json.dumps(requested_keywords),
                    requested_abstract,
                    requested_pages,
                    now,
                ),
            )
            conn.commit()

        return PaperDraft(
            draft_id=draft_id,
            paper_id=paper_id,
            requested_title=requested_title,
            requested_authors=requested_authors,
            requested_institution=requested_institution,
            requested_journal=requested_journal,
            requested_publish_date=requested_publish_date,
            requested_keywords=requested_keywords,
            requested_abstract=requested_abstract,
            requested_pages=requested_pages,
            created_at=now,
        )

    def publish_paper_draft(
        self,
        *,
        draft_id: str,
        title: str,
        authors: list[str],
        institution: str,
        journal: str,
        publish_date: str,
        keywords: list[str],
        abstract: str,
        pages: int,
        file_name: str,
        file_size: int,
    ) -> PaperDetail:
        with self.session_manager.connect() as conn:
            draft_row = conn.execute(
                "SELECT paper_id FROM academic_paper_drafts WHERE draft_id = ?",
                (draft_id,),
            ).fetchone()

            if not draft_row:
                raise ValueError(f"Draft not found: {draft_id}")

            paper_id = draft_row["paper_id"]
            now = datetime.now(timezone.utc).isoformat()

            conn.execute(
                """
                INSERT INTO academic_papers (
                    id, title, authors, institution, journal, publish_date,
                    keywords, abstract, downloads, pages, file_name, file_size,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    paper_id,
                    title,
                    json.dumps(authors),
                    institution,
                    journal,
                    publish_date,
                    json.dumps(keywords),
                    abstract,
                    0,
                    pages,
                    file_name,
                    file_size,
                    now,
                    now,
                ),
            )

            conn.execute("DELETE FROM academic_paper_drafts WHERE draft_id = ?", (draft_id,))
            conn.commit()

        return PaperDetail(
            paper_id=paper_id,
            title=title,
            authors=authors,
            institution=institution,
            journal=journal,
            publish_date=publish_date,
            keywords=keywords,
            downloads=0,
            pages=pages,
            file_size=file_size,
            file_name=file_name,
            abstract=abstract,
        )
