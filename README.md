# ChessMaster v2.4 — Human Coach Overlay

## Maia status clarified
The supplied v2.3 screenshot shows Maia returned a move (`e4`) and W/D/L output. That means the Maia UCI engine was running for that analysis. W/D/L is an expected game-outcome score after a move; it is NOT the probability that the opponent will choose that move. v2.4 explains this instead of showing the contradictory boilerplate.

## Human-readable coaching
- Replaces most UCI/SAN jargon with a short plain-English recommendation.
- Explains the basic purpose of the move (capture, check, central development, safer/active piece, pawn space).
- Explains how far the suggested move is from Stockfish's top choice in beginner-friendly language.
- Maia's predicted human move is described separately from Stockfish's objective recommendation.

## Screen overlay
- Removes the solid dark caption bar; the overlay window uses a transparent colour key and draws text/arrows only.
- Draws a short explanation beside the destination square.
- Adds a header switch: `Coach text: Bottom` / `Coach text: Top`.
- Keeps the green move arrow on the board.

## Limits
Explanations are deliberately short and based on move type; they are not deep natural-language tactical explanations. Maia predicts a likely human move at the selected Elo, while its W/D/L values should not be interpreted as move-choice probabilities. The overlay still requires a verified live position.
