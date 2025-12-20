# AlphaWrites

An easily accessible note-taking platform with markdown and LaTex support. Currently in early development. Alpha means just the beginning.

**Live at:** https://alphawrites.onrender.com 


## Core Functionality

Imagine a seamless experience: whenever an important piece of text, a fleeting thought, a new idea, a joke, an observation, or a journal entry comes to mind, you simply type or paste it into the application. You'll then assign relevant labels (e.g., "idea," "research," "journal," "project X") to categorize the entry effectively. Each note will be automatically timestamped, creating a chronological record.

## Vision

Our core concept is a sophisticated yet intuitive note-taking application designed to address the common challenge of organizing a diverse range of personal knowledge, journaling, ideas, jokes, and observations. The goal is to create a central, easily accessible (web, desktop, app, extensions), easily navigable "vault" for all your important textual information.

* This will likely follow a freemium model, where basic storage is free, and users can subscribe for additional capacity
* We are also thinking about a WhatsApp-like model, where users can backup their encrypted data as a vault in their favorite platform
* For risk-averse users:
    * Client-side encryption using a BIP39 seed phrase
    * This is a powerful security feature. It might be best offered as an optional (as it will reduce a few features like file editing, searching, etc.), advanced setting for privacy-focused users, rather than the default for everyone. A baseline of robust server-side encryption (at rest and in transit) would be essential regardless
* A browser extension for quick capture of web content and notes
* Integrating AI to automatically suggest titles for notes, polish text, and provide other smart writing aids
* Allowing users to make specific notes or collections public, creating shareable pages
* Quickly generating and managing to-do lists with minimal manual effort using AI or classical algorithms

## Local Development

Built with Python Flask.
```bash
pip install -r requirements.txt
```
```bash
python app.py
```
Typically available at `http://127.0.0.1:8000/`.

## Contact

Use [bravesamarth@gmail.com](mailto:bravesamarth@gmail.com) regarding any query.