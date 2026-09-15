This folder is auto-populated by launch-llm-fleet.ps1.

Every llama launcher .ps1 that gets launched is copied here (same
filename) if not already present. If a launcher ever disappears from
its original folder, the fleet falls back to the copy stored here.

Note: archived copies keep their original trailing self-invoke line
pointing at their original folder, so the crash-restart loop is inactive
while running from this folder. Restore the primary when possible.
