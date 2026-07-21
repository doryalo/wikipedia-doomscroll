"""Deterministic development fixtures for the local SQLite API."""

import hashlib
import json
from contextlib import closing

from .db import connect

DEMO_PASSWORD = "123"


def _hash_pw(password: str, salt: str) -> str:
    h = hashlib.sha256(f"{salt}:{password}".encode()).hexdigest()
    return f"{salt}:{h}"


def seed_demo_data() -> None:
    """Insert deterministic development records without replacing local data."""
    profiles = (
        ("profile-ada",    "ada",    _hash_pw(DEMO_PASSWORD, "seed-salt-ada")),
        ("profile-sam",    "sam",    _hash_pw(DEMO_PASSWORD, "seed-salt-sam")),
        ("profile-morgan", "morgan", _hash_pw(DEMO_PASSWORD, "seed-salt-morgan")),
        ("profile-riley",  "riley",  _hash_pw(DEMO_PASSWORD, "seed-salt-riley")),
    )
    characters = (
        ("character-cleopatra", "Cleopatra", "Last active ruler of the Ptolemaic Kingdom of Egypt.", "-0069-01-01", "-0030-08-12", "https://upload.wikimedia.org/wikipedia/commons/9/9e/Cleopatra_VII_Altes_Museum_Berlin.jpg"),
        ("character-leonardo", "Leonardo da Vinci", "Italian polymath of the High Renaissance.", "1452-04-15", "1519-05-02", "https://upload.wikimedia.org/wikipedia/commons/e/e2/Leonardo_da_Vinci_-_presumed_self-portrait_-_WGA12798.jpg"),
        ("character-tubman", "Harriet Tubman", "American abolitionist and political activist.", "1822-01-01", "1913-03-10", "https://upload.wikimedia.org/wikipedia/commons/0/0a/Harriet_Tubman_c1868-69.jpg"),
        ("character-curie", "Marie Curie", "Physicist and chemist who pioneered research on radioactivity.", "1867-11-07", "1934-07-04", "https://upload.wikimedia.org/wikipedia/commons/6/69/Marie_Curie_c1920.jpg"),
    )
    groups = (
        ("group-ancient-world", "Ancient World", "People, places, and events before 500 CE."),
        ("group-renaissance", "Renaissance", "Art, science, and politics of the Renaissance."),
        ("group-social-change", "Social Change", "Movements and people who changed society."),
        ("group-science", "Science History", "Discoveries and the people behind them."),
    )
    post_specs = (
        ("character-cleopatra", "A Mediterranean kingdom", "Egypt sat at the centre of trade and politics.", -51, "year", "51 BCE", ("ancient", "egypt"), ("group-ancient-world",)),
        ("character-leonardo", "A notebook page", "Ideas about anatomy, flight, and machines shared a single page.", 1489, "circa", "c. 1489", ("art", "invention"), ("group-renaissance", "group-science")),
        ("character-tubman", "A route to freedom", "The Underground Railroad was a network of people and safe places.", 1850, "circa", "c. 1850", ("abolition", "usa"), ("group-social-change",)),
        ("character-curie", "A new kind of research", "Careful measurements led to a new understanding of radioactivity.", 1898, "year", "1898", ("physics", "chemistry"), ("group-science",)),
        ("character-cleopatra", "Alliance with Caesar", "Roman politics became inseparable from Egypt's future.", -48, "year", "48 BCE", ("rome", "egypt"), ("group-ancient-world",)),
        ("character-leonardo", "The Last Supper", "A mural commission became one of the Renaissance's best-known paintings.", 1495, "range", "1495–1498", ("painting", "milan"), ("group-renaissance",)),
        ("character-tubman", "The Fugitive Slave Act", "The 1850 law increased the danger faced by freedom seekers.", 1850, "year", "1850", ("law", "abolition"), ("group-social-change",)),
        ("character-curie", "Polonium and radium", "The Curies announced two new elements in rapid succession.", 1898, "month", "July 1898", ("elements", "research"), ("group-science",)),
        ("character-cleopatra", "The Battle of Actium", "A naval battle reshaped the fate of the Roman Republic.", -31, "day", "2 September 31 BCE", ("naval", "rome"), ("group-ancient-world",)),
        ("character-leonardo", "The Mona Lisa", "Leonardo continued refining this portrait for years.", 1503, "circa", "c. 1503", ("painting", "florence"), ("group-renaissance",)),
        ("character-tubman", "Civil War service", "Tubman served as a nurse, scout, and spy for the Union Army.", 1863, "year", "1863", ("civil-war", "history"), ("group-social-change",)),
        ("character-curie", "First Nobel Prize", "Marie Curie shared the 1903 Nobel Prize in Physics.", 1903, "year", "1903", ("nobel", "physics"), ("group-science",)),
    )
    generated_topics = (
        ("character-cleopatra", "Alexandria", "A Mediterranean center for scholarship, trade, and diplomacy.", -50, "ancient", "egypt", ("group-ancient-world",)),
        ("character-leonardo", "Renaissance workshop", "Artists and engineers learned by observing, sketching, and making.", 1490, "renaissance", "art", ("group-renaissance", "group-science")),
        ("character-tubman", "Community networks", "Local organizers made information, travel, and mutual aid possible.", 1855, "social-change", "abolition", ("group-social-change",)),
        ("character-curie", "Laboratory notes", "Repeated experiments turned faint observations into reliable evidence.", 1900, "science", "research", ("group-science",)),
    )
    precision_cycle = ("year", "month", "day", "range", "circa")
    generated_specs = []
    for generated_index in range(88):
        character_id, theme, description, base_year, topic_tag, secondary_tag, post_groups = generated_topics[generated_index % len(generated_topics)]
        precision = precision_cycle[generated_index % len(precision_cycle)]
        year = base_year + (generated_index // len(generated_topics))
        sequence = generated_index + 1
        if precision == "month":
            date_label = f"March {year}"
        elif precision == "day":
            date_label = f"14 March {year}"
        elif precision == "range":
            date_label = f"{year}\u2013{year + 2}"
        elif precision == "circa":
            date_label = f"c. {year}"
        else:
            date_label = str(year)
        generated_specs.append(
            (
                character_id,
                f"{theme}: discovery {sequence}",
                f"{description} This fixture entry supports browsing and pagination tests.",
                year,
                precision,
                date_label,
                (topic_tag, secondary_tag, "fixture"),
                post_groups,
            )
        )
    post_specs += tuple(generated_specs)

    with closing(connect()) as connection:
        connection.executemany("INSERT OR IGNORE INTO profiles (id, username, password_hash) VALUES (?, ?, ?)", profiles)
        for pid, _uname, pw_hash in profiles:
            connection.execute(
                "UPDATE profiles SET password_hash = ? WHERE id = ? AND password_hash = 'demo-password-hash'",
                (pw_hash, pid),
            )
        connection.executemany("INSERT OR IGNORE INTO fictional_characters (id, name, description, birth_date, death_date, profile_photo_url) VALUES (?, ?, ?, ?, ?, ?)", characters)
        connection.executemany("INSERT OR IGNORE INTO groups (id, name, description) VALUES (?, ?, ?)", groups)
        for index, (character_id, title, content, year, precision, date_label, tags, post_groups) in enumerate(post_specs, start=1):
            post_id = f"post-{index:03d}"
            content_type = ("text", "image", "video", "reel")[(index - 1) % 4]
            media_url = None if content_type == "text" else f"https://images.example.test/wikipedia-doomscroll/{post_id}.{ 'jpg' if content_type == 'image' else 'mp4' }"
            created_at = (
                f"2026-07-21T12:{index:02d}:00.000Z"
                if index <= 12
                else f"2026-07-{20 - ((index - 13) // 24):02d}T{(index - 13) % 24:02d}:00:00.000Z"
            )
            connection.execute(
                """INSERT OR IGNORE INTO posts (id, fictional_character_id, title, content, media_url, content_type, thumbnail_url, historical_start_year, historical_precision, historical_date_label, label, tags, source_url, source_title, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (post_id, character_id, title, content, media_url, content_type, f"https://images.example.test/wikipedia-doomscroll/{post_id}-thumb.jpg" if content_type in ("video", "reel") else None, year, precision, date_label, "History", json.dumps(tags), f"https://en.wikipedia.org/wiki/{character_id.removeprefix('character-').replace('-', '_')}", title, created_at),
            )
            connection.executemany("INSERT OR IGNORE INTO post_groups (post_id, group_id) VALUES (?, ?)", ((post_id, group_id) for group_id in post_groups))
        connection.executemany("INSERT OR IGNORE INTO likes (profile_id, post_id) VALUES (?, ?)", (("profile-ada", "post-001"), ("profile-sam", "post-001"), ("profile-morgan", "post-002")))
        connection.executemany("INSERT OR IGNORE INTO comments (id, profile_id, post_id, content) VALUES (?, ?, ?, ?)", (("comment-001", "profile-sam", "post-001", "The date labels make this easy to explore."), ("comment-002", "profile-ada", "post-004", "A great starting point for science history.")))
        connection.executemany("INSERT OR IGNORE INTO profile_group_follows (profile_id, group_id) VALUES (?, ?)", (("profile-ada", "group-science"), ("profile-sam", "group-ancient-world")))
        connection.commit()
