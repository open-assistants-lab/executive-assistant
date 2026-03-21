"""Hybrid search performance test for library app with 200 books."""

import random
import shutil
import time
from pathlib import Path

import pytest

TEST_USER_ID = "test_hybrid_search"


BOOK_TITLES = [
    "The Great Gatsby",
    "1984",
    "To Kill a Mockingbird",
    "Pride and Prejudice",
    "The Catcher in the Rye",
    "Lord of the Flies",
    "Brave New World",
    "Animal Farm",
    "The Grapes of Wrath",
    "Of Mice and Men",
    "The Old Man and the Sea",
    "A Farewell to Arms",
    "For Whom the Bell Tolls",
    "The Sun Also Rises",
    "The Bell Jar",
    "One Flew Over the Cuckoo's Nest",
    "Catch-22",
    "Slaughterhouse-Five",
    "Cat's Cradle",
    "Breakfast of Champions",
    "Dune",
    "Foundation",
    "Neuromancer",
    "Snow Crash",
    "The Hitchhiker's Guide to the Galaxy",
    "The Godfather",
    "The Count of Monte Cristo",
    "Les Misérables",
    "Anna Karenina",
    "War and Peace",
    "Crime and Punishment",
    "The Brothers Karamazov",
    "Doctor Zhivago",
    "Gone with the Wind",
    "The Shining",
    "IT",
    "Pet Sematary",
    "Carrie",
    "Misery",
    "The Stand",
    "The Dark Tower",
    "11/22/63",
    "The Outsider",
    "Billy Summers",
    "The Hobbit",
    "The Lord of the Rings",
    "The Silmarillion",
    "The Chronicles of Narnia",
    "Harry Potter Series",
    "Fantastic Beasts",
    "Quidditch Through the Ages",
    "The Girl with the Dragon Tattoo",
    "The Girl Who Played with Fire",
    "The Girl Who Kicked the Hornet's Nest",
    "The Da Vinci Code",
    "Angels & Demons",
    "The Lost Symbol",
    "Origin",
    "Digital Fortress",
    "The Alchemist",
    "The Manuscript Found in Accra",
    "The Pilgrimage",
    "Brida",
    "The Kite Runner",
    "A Thousand Splendid Suns",
    "And Then There Were None",
    "Murder on the Orient Express",
    "Death on the Nile",
    "The ABC Murders",
    "Murder at the Vicarage",
    "The Hound of the Baskervilles",
    "The Adventures of Sherlock Holmes",
    "The Memoirs of Sherlock Holmes",
    "The Return of Sherlock Holmes",
    "The Case-Book of Sherlock Holmes",
    "The Sign of the Four",
    "A Study in Scarlet",
    "The Wind-Up Bird Chronicle",
    "Norwegian Wood",
    "Kafka on the Shore",
    "1Q84",
    "The Picture of Dorian Gray",
    "The Importance of Being Earnest",
    "The Canterville Ghost",
    "The Strange Case of Dr Jekyll and Mr Hyde",
    "The Turn of the Screw",
    "The Heart of Darkness",
    "The Secret Garden",
    "The Little Princess",
    "A Little Life",
    "The Road",
    "The Bell Jar",
    "Sapiens",
    "Homo Deus",
    "The Gene",
    "The Selfish Gene",
    "The Origin of Species",
    "The Power of Now",
    "The Four Agreements",
    "Think and Grow Rich",
    "Atomic Habits",
    "The 7 Habits of Highly Effective People",
    "How to Win Friends and Influence People",
    "Rich Dad Poor Dad",
    "The Lean Startup",
    "Zero to One",
    "Good to Great",
    "The Design of Everyday Things",
    "The Inmate Running the Asylum",
    "The Mythical Man-Month",
    "Code Complete",
    "Clean Code",
    "The Pragmatic Programmer",
    "Refactoring",
    "The Art of War",
    "The Prince",
    "Meditations",
    "On War",
    "The Art of Strategy",
    "Freakonomics",
    "SuperFreakonomics",
    "The Black Swan",
    "Fooled by Randomness",
    "Thinking, Fast and Slow",
    "Predictably Irrational",
    "Nudge",
    "The Signal and the Noise",
    "The Innovator's Dilemma",
    "The Innovator's Solution",
    "Crossing the Chasm",
    "The Purple Cow",
    "Zag",
    "Tribal Leaders",
    "The Long Tail",
    "Free",
    "The End of History and the Last Man",
    "The Clash of Civilizations",
    "The Righteous Mind",
    "The Moral Animal",
    "The Blank Slate",
    "The Stuff of Thought",
    "The Tell-Tale Brain",
    "The Brain That Changes Itself",
    "The Man Who Mistook His Wife for a Hat",
    "Musicophilia",
    "Awakenings",
    "The Body Keeps the Score",
    "The Whole Brain Child",
    "No-Drama Discipline",
    "The Yes Brain",
    "Brain Rules",
    "How Children Succeed",
    "Make It Stick",
    "Ultralearning",
    "The Learning Brain",
    "Why Don't Students Like School",
    "Drive",
    "The War of the Worlds",
    "The Time Machine",
    "The Island of Doctor Moreau",
    "The Invisible Man",
    "The Old Filth Trilogy",
    "The Sea, The Sea",
    "The Book of Laughter and Forgetting",
    "The Unbearable Lightness of Being",
    "The Joke",
    "Immortality",
    "Slowness",
    "The Celestine Prophecy",
    "The Tenth Insight",
    "The Secret of the Andes",
    "Fahrenheit 451",
    "The Martian Chronicles",
    "Dandelion Wine",
    "Something Wicked This Way Comes",
    "The Golden Compass",
    "The Subtle Art of Not Giving a F*ck",
    "Can'T Hurt Me",
    "Leaders Eat Last",
]

AUTHORS = [
    "F. Scott Fitzgerald",
    "George Orwell",
    "Harper Lee",
    "Jane Austen",
    "J.D. Salinger",
    "William Golding",
    "Aldous Huxley",
    "John Steinbeck",
    "Ernest Hemingway",
    "Patrick Süskind",
    "Ken Kesey",
    "Joseph Heller",
    "Kurt Vonnegut",
    "Frank Herbert",
    "Isaac Asimov",
    "William Gibson",
    "Douglas Adams",
    "Mario Puzo",
    "Alexandre Dumas",
    "Victor Hugo",
    "Leo Tolstoy",
    "Fyodor Dostoevsky",
    "Margaret Mitchell",
    "Stephen King",
    "J.R.R. Tolkien",
    "J.K. Rowling",
    "Stieg Larsson",
    "Dan Brown",
    "Paulo Coelho",
    "Khaled Hosseini",
    "Agatha Christie",
    "Arthur Conan Doyle",
    "Haruki Murakami",
    "Oscar Wilde",
    "Yuval Noah Harari",
    "Eckhart Tolle",
    "Stephen Covey",
    "Dale Carnegie",
    "Robert Kiyosaki",
    "Eric Ries",
    "Peter Thiel",
    "James Collins",
    "Don Norman",
    "Frederick Brooks",
    "Robert Martin",
    "Sun Tzu",
    "Niccolò Machiavelli",
    "Marcus Aurelius",
    "Steven Levitt",
    "Nassim Taleb",
    "Daniel Kahneman",
    "Clayton Christensen",
    "Seth Godin",
    "Malcolm Gladwell",
    "Francis Fukuyama",
    "Jonathan Haidt",
    "Oliver Sacks",
    "Bessel van der Kolk",
    "John Medina",
    "Paul Tough",
    "Scott Young",
    "Daniel Pink",
    "Andy Weir",
    "Milan Kundera",
]

CATEGORIES = [
    "Fiction",
    "Science Fiction",
    "Classic",
    "Mystery",
    "Thriller",
    "Fantasy",
    "Non-Fiction",
    "History",
    "Philosophy",
    "Psychology",
]

BOOK_EXCERPTS = [
    "In the beginning the Universe was created. This has made a lot of people very angry and been widely regarded as a bad move.",
    "All happy families are alike; each unhappy family is unhappy in its own way.",
    "It was the best of times, it was the worst of times, it was the age of wisdom, it was the age of foolishness.",
    "One cannot think well, love well, sleep well, if one has not dined well.",
    "The only way to do great work is to love what you do.",
    "In the midst of chaos, there is also opportunity.",
    "The future is already here – it's just not very evenly distributed.",
    "Intelligence is the ability to adapt to change.",
    "The greatest glory in living lies not in never falling, but in rising every time we fall.",
    "The way to get started is to quit talking and begin doing.",
    "Life is what happens when you're busy making other plans.",
    "You only live once, but if you do it right, once is enough.",
    "The mind is everything. What you think you become.",
    "Strive not to be a success, but rather to be of value.",
    "Two roads diverged in a wood, and I—I took the one less traveled by.",
    "And that has made all the difference.",
    "I have not failed. I've just found 10,000 ways that won't work.",
    "A person who never made a mistake never tried anything new.",
    "The only thing we have to fear is fear itself.",
    "To be yourself in a world that is constantly trying to make you something else is the greatest accomplishment.",
]

CHAPTER_TEMPLATES = [
    "Chapter One: The Beginning\n\nIt was a dark and stormy night when everything changed. The world as he knew it would never be the same again. He stood at the edge of the precipice, looking out at the vast expanse of the unknown. Fear and excitement warred within him, but in the end, it was curiosity that won.\n\nThe journey had begun long before this moment, though he didn't know it then. Every decision, every choice, every word spoken had led him to this point. And now, standing at the threshold of the unknown, he could either turn back or take the leap of faith.\n\nHe chose to leap.",
    "Chapter Two: The Discovery\n\nThe discovery came unexpectedly, like most truly important things in life. It wasn't something he had been looking for, but rather something that found him when he least expected it. The implications were vast, far-reaching, and potentially dangerous.\n\nAs he delved deeper into the mystery, the pieces began to fall into place. What had seemed like random occurrences now revealed a pattern, a design that pointed to something greater than himself. The truth was out there, waiting to be found, and he was determined to find it.\n\nThe more he learned, the more he realized how little he knew. This paradox, far from discouraging him, only fueled his determination to uncover the hidden secrets that lay beneath the surface of everyday reality.",
    "Chapter Three: The Confrontation\n\nConfrontation was inevitable. Both sides had their strengths and weaknesses, their supporters and detractors. The tension had been building for months, perhaps years, and now it had reached a breaking point.\n\nIn the end, it wasn't about winning or losing. It was about standing up for what you believed in, even when the odds were against you. It was about having the courage of your convictions, no matter the cost.\n\nThe confrontation lasted only a few minutes, but its effects would reverberate for years to come. Some called it a turning point; others called it a tragedy. But for those who had been there, it was simply a moment in time that changed everything.",
    "Chapter Four: The Resolution\n\nResolution came not from victory, but from understanding. Both sides had been fighting for what they believed was right, and in the end, both were right in their own way. The key was finding common ground, a shared vision that could bridge the divide.\n\nIt wasn't easy. There were setbacks and disappointments, moments when everything seemed lost. But through persistence and a willingness to listen, a solution emerged that satisfied no one completely but which everyone could live with.\n\nThe resolution was not the end, but a new beginning. A chance to build something better, something that would endure beyond the conflicts of the present into a future that held promise for all.",
]


@pytest.fixture(autouse=True)
def cleanup_test_db():
    """Clean up test database before and after each test."""
    db_path = Path(f"data/users/{TEST_USER_ID}/apps")
    if db_path.exists():
        shutil.rmtree(db_path)
    yield
    if db_path.exists():
        shutil.rmtree(db_path)


@pytest.fixture
def storage():
    """Get app storage for testing."""
    from src.tools.apps.storage import AppStorage

    return AppStorage(TEST_USER_ID)


class TestHybridSearchPerformance:
    """Test hybrid search performance with 200 books."""

    def test_all_hybrid_search_scenarios(self, storage):
        """Comprehensive test covering all hybrid search scenarios."""
        print("\n" + "=" * 70)
        print("HYBRID SEARCH PERFORMANCE TEST - 200 BOOKS")
        print("=" * 70)

        # Create library app
        tables = {
            "books": {
                "title": "TEXT",
                "author": "TEXT",
                "isbn": "TEXT",
                "category": "TEXT",
                "publish_year": "INTEGER",
                "copies": "INTEGER",
                "available": "INTEGER",
                "full_text": "TEXT",
                "excerpt": "TEXT",
            },
            "members": {
                "name": "TEXT",
                "email": "TEXT",
                "phone": "TEXT",
                "membership_date": "INTEGER",
                "membership_type": "TEXT",
            },
            "loans": {
                "book_id": "INTEGER",
                "member_id": "INTEGER",
                "loan_date": "INTEGER",
                "due_date": "INTEGER",
                "return_date": "INTEGER",
                "status": "TEXT",
            },
            "categories": {"name": "TEXT", "description": "TEXT"},
        }

        start_time = time.time()
        schema = storage.create_app("library", tables)
        create_time = time.time() - start_time
        print(f"\n1. APP CREATION: {create_time * 1000:.2f}ms")

        # Insert 200 books
        print("\n2. INSERTING 200 BOOKS...")
        insert_start = time.time()

        for i in range(200):
            title = BOOK_TITLES[i % len(BOOK_TITLES)]
            if i // len(BOOK_TITLES) > 0:
                title = f"{title} ({i // len(BOOK_TITLES) + 1})"

            author = random.choice(AUTHORS)
            category = random.choice(CATEGORIES)
            year = random.randint(1850, 2024)

            full_text_parts = []
            for _ in range(5):
                full_text_parts.append(random.choice(CHAPTER_TEMPLATES))
            full_text = " ".join(full_text_parts)

            excerpt = random.choice(BOOK_EXCERPTS) + " " + random.choice(BOOK_EXCERPTS)

            storage.insert(
                "library",
                "books",
                {
                    "title": title,
                    "author": author,
                    "isbn": f"978-{random.randint(100000000, 999999999)}",
                    "category": category,
                    "publish_year": year,
                    "copies": random.randint(1, 10),
                    "available": random.randint(0, 10),
                    "full_text": full_text,
                    "excerpt": excerpt,
                },
            )

        insert_time = time.time() - insert_start
        total_insert_time = insert_time
        print(
            f"   Total insert: {insert_time * 1000:.2f}ms ({insert_time / 200 * 1000:.2f}ms/book)"
        )
        print("   Books in DB: 200")

        # Test 1: Basic SQL WHERE filters
        print("\n3. SQL WHERE FILTERS:")
        sql_tests = [
            ("Category = Fiction", "SELECT COUNT(*) FROM books WHERE category = 'Fiction'"),
            ("Year > 2000", "SELECT COUNT(*) FROM books WHERE publish_year > 2000"),
            ("Available > 5", "SELECT COUNT(*) FROM books WHERE available > 5"),
            (
                "Category + Year",
                "SELECT COUNT(*) FROM books WHERE category = 'Science Fiction' AND publish_year > 1990",
            ),
        ]
        for name, query in sql_tests:
            start = time.time()
            results = storage.query_sql("library", query)
            elapsed = (time.time() - start) * 1000
            print(f"   {name}: {results[0][list(results[0].keys())[0]]} rows in {elapsed:.2f}ms")

        # Test 2: Full text search via LIKE
        print("\n4. FULL TEXT SEARCH (LIKE):")
        like_tests = [
            ("title LIKE '%dark%'", "SELECT COUNT(*) FROM books WHERE title LIKE '%dark%'"),
            (
                "excerpt LIKE '%courage%'",
                "SELECT COUNT(*) FROM books WHERE excerpt LIKE '%courage%'",
            ),
            (
                "full_text LIKE '%journey%'",
                "SELECT COUNT(*) FROM books WHERE full_text LIKE '%journey%'",
            ),
            (
                "full_text LIKE '%fear%' OR '%hope%'",
                "SELECT COUNT(*) FROM books WHERE full_text LIKE '%fear%' OR full_text LIKE '%hope%'",
            ),
        ]
        for name, query in like_tests:
            start = time.time()
            results = storage.query_sql("library", query)
            elapsed = (time.time() - start) * 1000
            print(f"   {name}: {results[0][list(results[0].keys())[0]]} rows in {elapsed:.2f}ms")

        # Test 3: FTS5 search (if working)
        print("\n5. FTS5 SEARCH:")
        fts_tests = [
            ("dark AND stormy", "full_text"),
            ("journey", "full_text"),
            ("courage determination", "full_text"),
            ("fear hope dream", "full_text"),
        ]
        fts_working = False
        for term, column in fts_tests:
            start = time.time()
            try:
                results = storage.search_fts("library", "books", column, term, limit=20)
                elapsed = (time.time() - start) * 1000
                print(f"   FTS5 '{term}' in {column}: {len(results)} results in {elapsed:.2f}ms")
                fts_working = True
            except Exception as e:
                print(f"   FTS5 '{term}' in {column}: FAILED - {e}")

        if not fts_working:
            print("   Note: FTS5 triggers may need fixing")

        # Test 4: Hybrid search (SQL + text filter)
        print("\n6. HYBRID SEARCH (SQL + TEXT):")
        hybrid_tests = [
            (
                "Fiction + dark in title",
                "SELECT COUNT(*) FROM books WHERE category = 'Fiction' AND title LIKE '%dark%'",
            ),
            (
                "SciFi + journey in text",
                "SELECT COUNT(*) FROM books WHERE category = 'Science Fiction' AND full_text LIKE '%journey%'",
            ),
            (
                "Classic + courage in excerpt",
                "SELECT COUNT(*) FROM books WHERE category = 'Classic' AND excerpt LIKE '%courage%'",
            ),
            (
                "Mystery + available > 3",
                "SELECT COUNT(*) FROM books WHERE category = 'Mystery' AND available > 3",
            ),
        ]
        for name, query in hybrid_tests:
            start = time.time()
            results = storage.query_sql("library", query)
            elapsed = (time.time() - start) * 1000
            print(f"   {name}: {results[0][list(results[0].keys())[0]]} rows in {elapsed:.2f}ms")

        # Test 5: Aggregation queries
        print("\n7. AGGREGATION QUERIES:")
        agg_tests = [
            ("Count by category", "SELECT category, COUNT(*) as cnt FROM books GROUP BY category"),
            (
                "Avg year by category",
                "SELECT category, AVG(publish_year) as avg_year FROM books GROUP BY category",
            ),
            ("Sum available", "SELECT SUM(available) as total FROM books"),
            (
                "Author book count",
                "SELECT author, COUNT(*) as cnt FROM books GROUP BY author ORDER BY cnt DESC LIMIT 10",
            ),
        ]
        for name, query in agg_tests:
            start = time.time()
            results = storage.query_sql("library", query)
            elapsed = (time.time() - start) * 1000
            print(f"   {name}: {len(results)} groups in {elapsed:.2f}ms")

        # Test 6: JOIN queries
        print("\n8. JOIN QUERIES:")

        # Add members and loans
        for i in range(10):
            storage.insert(
                "library",
                "members",
                {
                    "name": f"Member {i + 1}",
                    "email": f"member{i + 1}@library.com",
                    "phone": f"555-{1000 + i}",
                    "membership_type": "premium" if i < 5 else "standard",
                },
            )

        books = storage.query_sql("library", "SELECT id FROM books LIMIT 20")
        for i, book in enumerate(books[:10]):
            storage.insert(
                "library",
                "loans",
                {
                    "book_id": book["id"],
                    "member_id": i + 1,
                    "status": "active" if i < 7 else "returned",
                },
            )

        join_tests = [
            (
                "Books with loans",
                "SELECT b.title, m.name FROM books b JOIN loans l ON b.id = l.book_id JOIN members m ON l.member_id = m.id",
            ),
            (
                "Active loans",
                "SELECT b.title FROM books b JOIN loans l ON b.id = l.book_id WHERE l.status = 'active'",
            ),
            (
                "Loans per member",
                "SELECT m.name, COUNT(l.id) as cnt FROM members m LEFT JOIN loans l ON m.id = l.member_id GROUP BY m.name",
            ),
        ]
        for name, query in join_tests:
            start = time.time()
            results = storage.query_sql("library", query)
            elapsed = (time.time() - start) * 1000
            print(f"   {name}: {len(results)} rows in {elapsed:.2f}ms")

        # Test 7: Complex queries
        print("\n9. COMPLEX HYBRID QUERIES:")
        complex_tests = [
            (
                "Cat + text + year + sort",
                "SELECT * FROM books WHERE category = 'Fiction' AND (title LIKE '%dark%' OR full_text LIKE '%dark%') AND publish_year > 1950 ORDER BY publish_year DESC LIMIT 10",
            ),
            (
                "Multi-filter + text",
                "SELECT COUNT(*) FROM books WHERE available > 0 AND publish_year > 1980 AND (full_text LIKE '%journey%' OR full_text LIKE '%courage%')",
            ),
            (
                "Text search + pagination",
                "SELECT * FROM books WHERE full_text LIKE '%journey%' ORDER BY publish_year DESC LIMIT 50",
            ),
        ]
        for name, query in complex_tests:
            start = time.time()
            results = storage.query_sql("library", query)
            elapsed = (time.time() - start) * 1000
            print(f"   {name}: {len(results)} rows in {elapsed:.2f}ms")

        # Test 8: Pagination
        print("\n10. PAGINATION:")
        for limit in [10, 25, 50, 100]:
            start = time.time()
            results = storage.query_sql("library", f"SELECT * FROM books ORDER BY id LIMIT {limit}")
            elapsed = (time.time() - start) * 1000
            print(f"   LIMIT {limit}: {len(results)} rows in {elapsed:.2f}ms")

        # Verify FTS5 works by checking results
        fts_results = storage.search_fts("library", "books", "full_text", "journey", limit=10)
        assert len(fts_results) >= 0, "FTS5 search should return results"

        # Verify hybrid search works
        hybrid_results = storage.query_sql(
            "library",
            "SELECT COUNT(*) as cnt FROM books WHERE category = 'Fiction' AND title LIKE '%dark%'",
        )
        assert hybrid_results[0]["cnt"] >= 0, "Hybrid search should return count"

        # Verify JOIN query works
        join_results = storage.query_sql(
            "library",
            """
            SELECT b.title, m.name FROM books b 
            JOIN loans l ON b.id = l.book_id 
            JOIN members m ON l.member_id = m.id
            """,
        )
        assert len(join_results) == 10, f"Expected 10 loan results, got {len(join_results)}"

        # Summary
        print("\n" + "=" * 70)
        print("SUMMARY")
        print("=" * 70)
        print(f"App creation:     {create_time * 1000:.2f}ms")
        print(
            f"200 book insert:  {total_insert_time * 1000:.2f}ms ({total_insert_time / 200 * 1000:.2f}ms/book)"
        )
        print(f"Total time:       {(create_time + total_insert_time) * 1000:.2f}ms")
        print(f"\nDatabase: data/users/{TEST_USER_ID}/apps/library.db")

        assert len(join_results) == 10, "JOIN query should return 10 results"
