# LLaDA-Rec diffusion fixture

This is a deidentified deterministic contract fixture. It preserves the pinned
official implementation's all-mask initialization, confidence-selected
position order, position-valid vocabulary, beam ancestry, monotone unmasking,
semantic-ID ambiguity, and ranked-item resolution. It contains no upstream
source, Amazon data, tokenizer artifact, checkpoint, or trained output.

The expected-failure mutation attempts to remask an already filled position.
That transition is rejected because the pinned official inference code never
remasks filled positions.
