"""Stable method-family identities shared by contracts, SDK, and trace layers."""

METHOD_FAMILY_PAYLOAD_SCHEMAS = {
    "autoregressive_prefix": "sidscope.trace_payload.autoregressive_prefix.v1",
    "parallel_graph_token_set": "sidscope.trace_payload.parallel_graph_token_set.v1",
    "masked_diffusion": "sidscope.trace_payload.masked_diffusion.v1",
    "latent_retry": "sidscope.trace_payload.latent_retry.v1",
    "decoder_overlay": "sidscope.trace_payload.decoder_overlay.v1",
}

METHOD_FAMILIES = frozenset(METHOD_FAMILY_PAYLOAD_SCHEMAS)
