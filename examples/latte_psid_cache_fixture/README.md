# Latte/PSID Cache Contract Fixture

This directory is a deidentified, bounded schema fixture shaped like the
official Latte/PSID processed cache. It is not an Amazon Reviews artifact, an
official-code-derived `.sem_ids` cache, or evidence of a trained generator.

The positive route validates PAD-aware item identity, complete catalog joins,
conflict-free semantic IDs, PSID/Latte vocabulary offsets, ordered
autoregressive state, latent-path aggregation, and ranked-item export. The
manifest also declares an expected `semantic_id_collision` failure.
