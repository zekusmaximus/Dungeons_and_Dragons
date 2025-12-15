# Dungeons & Dragons Game Manual

## Introduction

Welcome to the Dungeons & Dragons (D&D) digital gaming platform! This application provides a comprehensive tool for running tabletop RPG campaigns, featuring deterministic dice rolls for consistent gameplay and file-based storage for persistent, shareable campaign data. Whether you're a Dungeon Master (DM) or a player, this guide will help you navigate the system and enjoy immersive adventures.

Key features include:
- Deterministic dice mechanics using pre-generated entropy for fair, reproducible rolls
- File-based campaign storage allowing easy backups, sharing, and version control
- Web-based UI for intuitive gameplay management
- Modular backend supporting character creation, combat, exploration, and more

## Getting Started

### Prerequisites
- Python 3.8+ for the backend service
- Node.js and npm for the frontend UI
- Git for version control (optional but recommended)

### Installation
1. Clone or download the project repository to your local machine.
2. Navigate to the project root directory (`c:/Users/zeke/Desktop/Projects/Dungeons_and_Dragons`).
3. Install backend dependencies:
   ```
   pip install -r service/requirements.txt
   ```
4. Install frontend dependencies:
   ```
   cd ui
   npm install
   cd ..
   ```

### Running the Application
1. Start the backend service from the project root directory:
   ```
   uvicorn service.app:app --reload
   ```
   Note: Ensure your working directory is the project root (c:/Users/zeke/Desktop/Projects/Dungeons_and_Dragons) before running this command.
2. In a separate terminal, start the frontend UI:
   ```
   cd ui
   npm run dev
   ```
3. Open your web browser and navigate to `http://localhost:5173` (or the port specified by Vite).

### Creating Your First Session
1. Upon launching the UI, you'll see the Lobby component.
2. Click "New Session" to create a new campaign.
3. Choose a session name and initial settings.
4. The system will generate a new directory under `sessions/` with your campaign data.

## Gameplay Mechanics

### Character Creation
- Use the character creation module to build player characters (PCs) and non-player characters (NPCs).
- Select race, class, background, and abilities from predefined tables.
- Characters are stored as JSON files in the `characters/` directory for easy editing and sharing.

### Combat
- Engage in turn-based combat using the combat calculator.
- Roll deterministic dice for attacks, damage, and saving throws.
- Manage initiative, advantage/disadvantage, and stances.
- Combat logs are recorded in session transcripts for review.

### Exploration
- Navigate hex-based maps and encounter random events.
- Use exploration beats and scene types to drive narrative.
- Terrain and movement modifiers affect travel.

### Downtime Activities
- Between adventures, characters can pursue business ventures, carousing, crafting, research, and training.
- These activities use downtime rules and can earn experience or resources.

### Narrative Elements
- Incorporate flashbacks, tone dials, and scene framing for rich storytelling.
- Manage quests, mysteries, factions, and rumors to build campaign depth.

## UI Components

### Lobby
The main entry point for managing sessions. View existing campaigns, create new ones, or join active games.

### Turn Console
Central hub for gameplay actions. Submit commands, view turn results, and manage initiative.

### Schema Form
Dynamic form generator for editing game entities like characters, quests, and encounters. Validates input against JSON schemas.

### Clock Visualization
Visual representation of campaign timeline and events.

### Jobs Drawer
Monitor background processes and long-running tasks.

### Quest Editor
Create and modify quest structures with objectives and rewards.

### Diff Viewer
Compare changes between session snapshots for auditing.

### Export Bundle
Package campaign data for sharing or backup.

## Advanced Features

### Deterministic Dice
- Dice rolls use pre-computed entropy from `dice/entropy.ndjson`.
- Ensures reproducible results for fair play and debugging.
- Verify rolls using the `dice/verify_dice.py` script.

### File-Based Storage
- All campaign data stored as files in the project directory.
- Sessions in `sessions/`, characters in `characters/`, data in `data/`.
- Enables version control with Git, easy backups, and cross-platform compatibility.

### Snapshots and Journaling
- Automatic snapshots capture game state at key points.
- Journal entries track narrative progress.
- Changelog documents changes for transparency.

### Rules Integration
- Searchable rules index for quick reference.
- Tables for encounters, treasure, weather, and more.
- Customizable through JSON files.

### API and Extensibility
- RESTful API via FastAPI backend.
- Modular design allows adding new features via Python modules.
- Docker support for containerized deployment.

## FAQs

### Q: How do I roll dice?
A: Dice rolls are handled deterministically by the system. When you perform an action requiring a roll, the backend selects the next entropy value and computes the result.

### Q: Can I play offline?
A: Yes, the file-based nature allows running the application locally without internet. However, real-time multiplayer features may require network connectivity.

### Q: How do I backup my campaign?
A: Simply copy the entire project directory or use Git to commit changes. Session data is stored in `sessions/[session-name]/`.

### Q: What if I make a mistake in a turn?
A: Use the snapshot system to revert to previous states. The changelog helps track what changed.

### Q: Can I customize rules or add homebrew content?
A: Absolutely! Modify JSON files in `tables/`, `data/`, or create new modules in the appropriate directories. The schema system ensures compatibility.

### Q: How do I add new characters or monsters?
A: Use the character creation tools or manually edit JSON files in `data/characters/` and `data/monsters/`. Validate using the provided schemas.

### Q: Is this compatible with official D&D rules?
A: The system is designed to support D&D 5th Edition rules, with some customizations for digital play. Check `rules_index/` for specific implementations.

### Q: Troubleshooting: UI not loading
A: Ensure both backend and frontend are running. Check console for errors. Try clearing browser cache or reinstalling dependencies.

### Q: Troubleshooting: Backend errors
A: Check `service/app.py` logs. Ensure all Python dependencies are installed. Verify file permissions in the project directory.

### Q: Troubleshooting: 404 error on /api/sessions
A: After updating vite.config.ts for proxy rewrite changes, the UI dev server MUST be restarted (npm run dev) for the changes to take effect.

### Q: Troubleshooting: 500 Internal Server Error on API calls
A: This may be due to missing or corrupted session files, missing world data, or backend code issues. Check backend logs for details. Ensure session directories contain required files like state.json, turn.md, etc. Verify that world data exists and is accessible.

For more help, consult the README.md, ENGINE.md, or PROTOCOL.md files in the project root.