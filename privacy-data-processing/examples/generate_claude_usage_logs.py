"""Generate simulated Claude usage logs for CLIO-style analysis.

This script generates realistic Claude conversation logs that include:
- Realistic user queries and Claude responses
- PII (emails, names, IPs) to demonstrate privacy preservation
- Various conversation types (coding, writing, research, etc.)
- Metadata (timestamps, user IDs, topics, etc.)

This simulates the actual data that Anthropic's CLIO team would analyze.
"""

import random
import string
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any
import polars as pl
from rich.console import Console
from rich.progress import track

console = Console()

# Seed for reproducibility
random.seed(42)


class ClaudeUsageSimulator:
    """Generates realistic Claude conversation logs."""

    def __init__(self):
        self.conversation_types = {
            "coding": 0.35,  # 35% coding help
            "writing": 0.25,  # 25% writing assistance
            "research": 0.20,  # 20% research/analysis
            "creative": 0.10,  # 10% creative writing
            "general": 0.10,  # 10% general chat
        }

        self.coding_topics = [
            "Python debugging",
            "React component",
            "SQL query",
            "API design",
            "Algorithm optimization",
            "Code review",
            "Unit testing",
            "Async programming",
            "Data structures",
            "System design",
            "Docker configuration",
            "Git workflow",
        ]

        self.writing_topics = [
            "Email draft",
            "Blog post",
            "Technical documentation",
            "Resume",
            "Cover letter",
            "Product description",
            "Marketing copy",
            "Report summary",
        ]

        self.research_topics = [
            "Literature review",
            "Data analysis",
            "Market research",
            "Competitor analysis",
            "Technical comparison",
            "Trend analysis",
            "Statistical analysis",
            "Survey design",
        ]

    def generate_conversation(self, conv_id: int, conv_type: str) -> Dict[str, Any]:
        """Generate a single conversation."""

        # Generate user information with PII
        user_name = self._generate_name()
        user_email = self._generate_email(user_name)
        user_ip = self._generate_ip()
        user_id = f"user_{random.randint(1000, 999999)}"

        # Generate conversation
        if conv_type == "coding":
            user_message, assistant_response, topic = self._generate_coding_conversation()
        elif conv_type == "writing":
            user_message, assistant_response, topic = self._generate_writing_conversation()
        elif conv_type == "research":
            user_message, assistant_response, topic = self._generate_research_conversation()
        elif conv_type == "creative":
            user_message, assistant_response, topic = self._generate_creative_conversation()
        else:
            user_message, assistant_response, topic = self._generate_general_conversation()

        # Generate metadata
        timestamp = datetime.now() - timedelta(
            days=random.randint(0, 365), hours=random.randint(0, 23), minutes=random.randint(0, 59)
        )

        # Add some PII to messages
        user_message = self._inject_pii(user_message, user_name, user_email)

        return {
            "conversation_id": f"conv_{conv_id}",
            "user_id": user_id,
            "user_name": user_name,
            "user_email": user_email,
            "user_ip": user_ip,
            "timestamp": timestamp.isoformat(),
            "conversation_type": conv_type,
            "topic": topic,
            "user_message": user_message,
            "assistant_response": assistant_response,
            "message_count": random.randint(2, 20),
            "total_tokens": random.randint(500, 8000),
            "model": random.choice(["claude-3-opus", "claude-3-sonnet", "claude-3-haiku"]),
            "region": random.choice(["us-east-1", "us-west-2", "eu-west-1", "ap-southeast-1"]),
            "session_duration_seconds": random.randint(60, 3600),
        }

    def _generate_coding_conversation(self):
        """Generate coding-related conversation."""
        topic = random.choice(self.coding_topics)

        user_templates = [
            f"I'm having trouble with {topic}. Can you help me debug this code?",
            f"How do I implement {topic} in my project?",
            f"What's the best practice for {topic}?",
            f"I need help optimizing {topic}. Here's my current implementation...",
            f"Can you review my {topic} code and suggest improvements?",
        ]

        assistant_templates = [
            f"I'd be happy to help with {topic}. Based on the code you shared, I see a few issues...",
            f"For {topic}, here's a recommended approach with detailed explanation...",
            f"Let me walk you through {topic} step by step with examples...",
            f"I can help optimize your {topic} implementation. Here are some suggestions...",
        ]

        return random.choice(user_templates), random.choice(assistant_templates), topic

    def _generate_writing_conversation(self):
        """Generate writing assistance conversation."""
        topic = random.choice(self.writing_topics)

        user_templates = [
            f"Can you help me write a {topic}?",
            f"I need to create a professional {topic}. Can you assist?",
            f"Please review and improve this {topic} draft...",
            f"What should I include in a {topic}?",
        ]

        assistant_templates = [
            f"I'll help you create a {topic}. Here's a well-structured draft...",
            f"For your {topic}, here's a professional version with improvements...",
            f"Let me suggest enhancements to your {topic}...",
        ]

        return random.choice(user_templates), random.choice(assistant_templates), topic

    def _generate_research_conversation(self):
        """Generate research-related conversation."""
        topic = random.choice(self.research_topics)

        user_templates = [
            f"I need help with {topic}. Where should I start?",
            f"Can you analyze this data for {topic}?",
            f"What methodology should I use for {topic}?",
            f"Help me understand {topic} in the context of...",
        ]

        assistant_templates = [
            f"For {topic}, I recommend starting with these key areas...",
            f"Based on the data, here's my analysis for {topic}...",
            f"Let me break down {topic} into actionable steps...",
        ]

        return random.choice(user_templates), random.choice(assistant_templates), topic

    def _generate_creative_conversation(self):
        """Generate creative writing conversation."""
        topics = ["Short story", "Poem", "Character development", "Plot outline", "Dialogue"]
        topic = random.choice(topics)

        user_templates = [
            f"Write a {topic} about...",
            f"Help me brainstorm ideas for a {topic}",
            f"Can you improve this {topic}?",
        ]

        assistant_templates = [
            f"Here's a {topic} based on your request...",
            f"I've created a {topic} with these elements...",
        ]

        return random.choice(user_templates), random.choice(assistant_templates), topic

    def _generate_general_conversation(self):
        """Generate general conversation."""
        topics = ["General question", "Explanation", "Advice", "Discussion", "Information"]
        topic = random.choice(topics)

        user_templates = [
            "Can you explain...",
            "What's your opinion on...",
            "Help me understand...",
            "I have a question about...",
        ]

        assistant_templates = [
            "Let me explain that...",
            "Based on the context...",
            "Here's what you should know...",
        ]

        return random.choice(user_templates), random.choice(assistant_templates), topic

    def _generate_name(self) -> str:
        """Generate a realistic name."""
        first_names = [
            "James",
            "Mary",
            "John",
            "Patricia",
            "Robert",
            "Jennifer",
            "Michael",
            "Linda",
            "William",
            "Elizabeth",
            "David",
            "Barbara",
            "Richard",
            "Susan",
            "Joseph",
            "Jessica",
            "Thomas",
            "Sarah",
            "Charles",
            "Karen",
            "Daniel",
            "Nancy",
            "Matthew",
            "Lisa",
        ]
        last_names = [
            "Smith",
            "Johnson",
            "Williams",
            "Brown",
            "Jones",
            "Garcia",
            "Miller",
            "Davis",
            "Rodriguez",
            "Martinez",
            "Hernandez",
            "Lopez",
            "Gonzalez",
            "Wilson",
            "Anderson",
            "Thomas",
            "Taylor",
            "Moore",
            "Jackson",
            "Martin",
            "Lee",
            "Thompson",
            "White",
        ]
        return f"{random.choice(first_names)} {random.choice(last_names)}"

    def _generate_email(self, name: str) -> str:
        """Generate email from name."""
        domains = ["gmail.com", "yahoo.com", "outlook.com", "company.com", "email.com"]
        name_parts = name.lower().split()
        patterns = [
            f"{name_parts[0]}.{name_parts[1]}",
            f"{name_parts[0][0]}{name_parts[1]}",
            f"{name_parts[0]}_{name_parts[1]}",
            f"{name_parts[0]}{name_parts[1][0]}",
        ]
        return f"{random.choice(patterns)}@{random.choice(domains)}"

    def _generate_ip(self) -> str:
        """Generate a random IP address."""
        return f"{random.randint(1, 255)}.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(1, 255)}"

    def _inject_pii(self, message: str, name: str, email: str) -> str:
        """Inject PII into message for privacy demo."""
        if random.random() < 0.3:  # 30% chance to include name
            message = f"{message} My name is {name}."

        if random.random() < 0.2:  # 20% chance to include email
            message = f"{message} You can reach me at {email}."

        if random.random() < 0.1:  # 10% chance to include phone
            phone = f"({random.randint(200, 999)}) {random.randint(100, 999)}-{random.randint(1000, 9999)}"
            message = f"{message} Call me at {phone}."

        return message

    def generate_dataset(self, num_conversations: int = 100000) -> pl.DataFrame:
        """Generate complete dataset of conversations."""
        console.print(f"[cyan]Generating {num_conversations:,} Claude conversation logs...[/cyan]")

        # Determine conversation types based on distribution
        conversations = []
        for i in track(range(num_conversations), description="Generating conversations"):
            # Select conversation type based on distribution
            rand = random.random()
            cumulative = 0
            conv_type = "general"

            for ctype, prob in self.conversation_types.items():
                cumulative += prob
                if rand < cumulative:
                    conv_type = ctype
                    break

            conv = self.generate_conversation(i, conv_type)
            conversations.append(conv)

        # Convert to DataFrame
        df = pl.DataFrame(conversations)

        console.print(f"[green]✓ Generated {len(df):,} conversations[/green]")

        # Show statistics
        console.print("\n[bold]Conversation Type Distribution:[/bold]")
        type_counts = (
            df.group_by("conversation_type")
            .agg(pl.count().alias("count"))
            .sort("count", descending=True)
        )
        for row in type_counts.iter_rows(named=True):
            console.print(
                f"  {row['conversation_type']}: {row['count']:,} ({row['count']/len(df)*100:.1f}%)"
            )

        console.print(f"\n[bold]Model Distribution:[/bold]")
        model_counts = (
            df.group_by("model").agg(pl.count().alias("count")).sort("count", descending=True)
        )
        for row in model_counts.iter_rows(named=True):
            console.print(f"  {row['model']}: {row['count']:,}")

        console.print(f"\n[bold]Regions:[/bold]")
        region_counts = (
            df.group_by("region").agg(pl.count().alias("count")).sort("count", descending=True)
        )
        for row in region_counts.iter_rows(named=True):
            console.print(f"  {row['region']}: {row['count']:,}")

        return df


def main():
    """Generate Claude usage logs."""
    import argparse

    parser = argparse.ArgumentParser(description="Generate simulated Claude usage logs")
    parser.add_argument(
        "--conversations",
        type=int,
        default=100000,
        help="Number of conversations to generate (default: 100,000)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="demo_data/claude_usage_logs.parquet",
        help="Output file path (default: demo_data/claude_usage_logs.parquet)",
    )

    args = parser.parse_args()

    console.print("\n[bold cyan]Claude Usage Log Simulator[/bold cyan]")
    console.print("Generating realistic conversation data for CLIO-style analysis\n")

    # Create simulator
    simulator = ClaudeUsageSimulator()

    # Generate dataset
    df = simulator.generate_dataset(num_conversations=args.conversations)

    # Save to disk
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(output_path, compression="zstd")

    file_size = output_path.stat().st_size / 1024 / 1024
    console.print(f"\n[green]✓ Saved to {output_path}[/green]")
    console.print(f"  File size: {file_size:.1f} MB")
    console.print(f"  Total conversations: {len(df):,}")
    console.print(f"  Total tokens: {df['total_tokens'].sum():,}")

    # Show sample
    console.print("\n[bold]Sample Conversations:[/bold]")
    for i, row in enumerate(df.head(3).iter_rows(named=True)):
        console.print(f"\n{i+1}. [{row['conversation_type'].upper()}] {row['topic']}")
        console.print(f"   User: {row['user_name']} ({row['user_email']})")
        console.print(f"   IP: {row['user_ip']}")
        console.print(f"   Model: {row['model']}")
        console.print(f"   Message: {row['user_message'][:100]}...")

    console.print("\n[bold green]✓ Claude usage logs generated successfully![/bold green]")
    console.print("\n[bold]Next Steps:[/bold]")
    console.print("1. Analyze with privacy preservation:")
    console.print(
        f"   [cyan]python -m data_processing process {output_path} demo_output/ --enable-pii[/cyan]"
    )
    console.print("\n2. Cluster conversations by topic:")
    console.print(
        f"   [cyan]python -m data_processing cluster {output_path} user_message --num-clusters 10[/cyan]"
    )
    console.print("\n3. Run quality check:")
    console.print(f"   [cyan]python -m data_processing quality-check {output_path}[/cyan]")
    console.print()


if __name__ == "__main__":
    try:
        from rich.console import Console
        from rich.progress import track
    except ImportError:
        print("Installing required packages...")
        import subprocess

        subprocess.run(["pip", "install", "rich"], check=True)
        from rich.console import Console
        from rich.progress import track

    main()
