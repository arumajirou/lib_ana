# CLE V6 batch codegen / module=timesfm / total=100

# --- function: timesfm.flax.transformer.make_attn_mask
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.flax.transformer import make_attn_mask

result = make_attn_mask(
    query_length=None  # TODO: int,
    num_all_masked_kv=None  # TODO: Integer[Array, 'b'],
    query_index_offset=None,
    kv_length=0,
)

# --- function: timesfm.flax.util.revin
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.flax.util import revin

result = revin(
    x=None  # TODO: Float[Array, 'b ...'],
    mu=None  # TODO: Float[Array, 'b ...'],
    sigma=None  # TODO: Float[Array, 'b ...'],
    reverse=False,
)

# --- function: timesfm.flax.util.scan_along_axis
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.flax.util import scan_along_axis

result = scan_along_axis(
    f=None  # TODO,
    init=None  # TODO,
    xs=None  # TODO,
    axis=None  # TODO: int,
    kwargs=None  # TODO,
)

# --- function: timesfm.flax.util.update_running_stats
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.flax.util import update_running_stats

result = update_running_stats(
    n=None  # TODO: Float[Array, 'b'],
    mu=None  # TODO: Float[Array, 'b'],
    sigma=None  # TODO: Float[Array, 'b'],
    x=None  # TODO: Float[Array, 'b p'],
    mask=None  # TODO: Bool[Array, 'b p'],
)

# --- function: timesfm.timesfm_2p5.timesfm_2p5_base.linear_interpolation
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.timesfm_2p5.timesfm_2p5_base import linear_interpolation

result = linear_interpolation(
    arr=None  # TODO,
)

# --- function: timesfm.timesfm_2p5.timesfm_2p5_base.strip_leading_nans
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.timesfm_2p5.timesfm_2p5_base import strip_leading_nans

result = strip_leading_nans(
    arr=None  # TODO,
)

# --- function: timesfm.timesfm_2p5.timesfm_2p5_flax._after_model_decode
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.timesfm_2p5.timesfm_2p5_flax import _after_model_decode

result = _after_model_decode(
    fc=None  # TODO,
    pf_outputs=None  # TODO,
    quantile_spreads=None  # TODO,
    ar_outputs=None  # TODO,
    flipped_pf_outputs=None  # TODO,
    flipped_quantile_spreads=None  # TODO,
    flipped_ar_outputs=None  # TODO,
    is_positive=None  # TODO,
    mu=None  # TODO,
    sigma=None  # TODO,
    p=None  # TODO,
)

# --- function: timesfm.timesfm_2p5.timesfm_2p5_flax._apply_stacked_transformers
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.timesfm_2p5.timesfm_2p5_flax import _apply_stacked_transformers

result = _apply_stacked_transformers(
    model=None  # TODO: transformer.Transformer,
    x=None  # TODO: Float[Array, 'b n d'],
    m=None  # TODO: Float[Array, 'b n'],
    decode_cache=None,
)

# --- function: timesfm.timesfm_2p5.timesfm_2p5_flax._before_model_decode
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.timesfm_2p5.timesfm_2p5_flax import _before_model_decode

result = _before_model_decode(
    fc=None  # TODO,
    inputs=None  # TODO,
    masks=None  # TODO,
)

# --- function: timesfm.timesfm_2p5.timesfm_2p5_flax._create_stacked_transformers
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.timesfm_2p5.timesfm_2p5_flax import _create_stacked_transformers

result = _create_stacked_transformers(
    config=None  # TODO: configs.StackedTransformersConfig,
    key=None  # TODO: jax.Array,
)

# --- function: timesfm.timesfm_2p5.timesfm_2p5_flax._fix_quantile_crossing_fn
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.timesfm_2p5.timesfm_2p5_flax import _fix_quantile_crossing_fn

result = _fix_quantile_crossing_fn(
    full_forecast=None  # TODO,
)

# --- function: timesfm.timesfm_2p5.timesfm_2p5_flax._flip_quantile_fn
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.timesfm_2p5.timesfm_2p5_flax import _flip_quantile_fn

result = _flip_quantile_fn(
    x=None  # TODO,
)

# --- function: timesfm.timesfm_2p5.timesfm_2p5_flax._force_flip_invariance_fn
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.timesfm_2p5.timesfm_2p5_flax import _force_flip_invariance_fn

result = _force_flip_invariance_fn(
    flipped_pf_outputs=None  # TODO,
    flipped_quantile_spreads=None  # TODO,
    flipped_ar_outputs=None  # TODO,
)

# --- function: timesfm.timesfm_2p5.timesfm_2p5_flax._scan_along_axis
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.timesfm_2p5.timesfm_2p5_flax import _scan_along_axis

result = _scan_along_axis(
    f=None  # TODO,
    init=None  # TODO,
    xs=None  # TODO,
    axis=None  # TODO: int,
    kwargs=None  # TODO,
)

# --- function: timesfm.timesfm_2p5.timesfm_2p5_flax._use_continuous_quantile_head_fn
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.timesfm_2p5.timesfm_2p5_flax import _use_continuous_quantile_head_fn

result = _use_continuous_quantile_head_fn(
    full_forecast=None  # TODO,
    quantile_spreads=None  # TODO,
    max_horizon=None  # TODO,
)

# --- function: timesfm.timesfm_2p5.timesfm_2p5_flax.try_gc
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.timesfm_2p5.timesfm_2p5_flax import try_gc

result = try_gc(
)

# --- function: timesfm.torch.transformer._dot_product_attention
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.torch.transformer import _dot_product_attention

result = _dot_product_attention(
    query=None  # TODO,
    key=None  # TODO,
    value=None  # TODO,
    mask=None,
)

# --- function: timesfm.torch.transformer._torch_dot_product_attention
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.torch.transformer import _torch_dot_product_attention

result = _torch_dot_product_attention(
    query=None  # TODO,
    key=None  # TODO,
    value=None  # TODO,
    mask=None,
)

# --- function: timesfm.torch.transformer.make_attn_mask
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.torch.transformer import make_attn_mask

result = make_attn_mask(
    query_length=None  # TODO: int,
    num_all_masked_kv=None  # TODO: torch.Tensor,
    query_index_offset=None,
    kv_length=0,
)

# --- function: timesfm.torch.util.revin
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.torch.util import revin

result = revin(
    x=None  # TODO: torch.Tensor,
    mu=None  # TODO: torch.Tensor,
    sigma=None  # TODO: torch.Tensor,
    reverse=False,
)

# --- function: timesfm.torch.util.update_running_stats
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.torch.util import update_running_stats

result = update_running_stats(
    n=None  # TODO: torch.Tensor,
    mu=None  # TODO: torch.Tensor,
    sigma=None  # TODO: torch.Tensor,
    x=None  # TODO: torch.Tensor,
    mask=None  # TODO: torch.Tensor,
)

# --- function: timesfm.utils.xreg_lib._repeat
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.utils.xreg_lib import _repeat

result = _repeat(
    elements=None  # TODO: Iterable[Any],
    counts=None  # TODO: Iterable[int],
)

# --- function: timesfm.utils.xreg_lib._to_padded_jax_array
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.utils.xreg_lib import _to_padded_jax_array

result = _to_padded_jax_array(
    x=None  # TODO: np.ndarray,
)

# --- function: timesfm.utils.xreg_lib._unnest
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.utils.xreg_lib import _unnest

result = _unnest(
    nested=None  # TODO: Sequence[Sequence[Any]],
)

# --- function: timesfm.utils.xreg_lib.normalize
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.utils.xreg_lib import normalize

result = normalize(
    batch=None  # TODO,
)

# --- function: timesfm.utils.xreg_lib.renormalize
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.utils.xreg_lib import renormalize

result = renormalize(
    batch=None  # TODO,
    stats=None  # TODO,
)

# --- class: timesfm.configs.ForecastConfig
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.configs import ForecastConfig

# 予測設定の作成
# TODO: 用途に合わせて各パラメータを調整してください
obj = ForecastConfig(
    max_context=0,  # モデルに入力する最大過去データ点数
    max_horizon=0,  # 一度に予測する最大ステップ数
    normalize_inputs=False,  # 入力データを正規化するか
    window_size=0,  # 分解予測時のウィンドウサイズ
    per_core_batch_size=1,  # コアごとのバッチサイズ
    use_continuous_quantile_head=False,  # 連続分位点ヘッドを使用するか
    force_flip_invariance=True,  # 反転不変性を強制するか
    infer_is_positive=True,  # 出力が非負であることを保証するか
    fix_quantile_crossing=False,  # 分位点の交差を修正するか
    return_backcast=False,  # 過去データの再構成を返すか
)

print(f"ForecastConfig created: context={obj.max_context}, horizon={obj.max_horizon}")

# --- class: timesfm.configs.RandomFourierFeaturesConfig
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.configs import RandomFourierFeaturesConfig

# ランダムフーリエ特徴量レイヤーの設定作成
# TODO: 用途に合わせて各パラメータを調整してください
obj = RandomFourierFeaturesConfig(
    input_dims=None  # TODO: int,  # 入力次元数
    output_dims=None  # TODO: int,  # 出力次元数
    projection_stddev=None  # TODO: float,  # 投影重みの初期化標準偏差
    use_bias=None  # TODO: bool,  # バイアス項を使用するか
)

print(f"RFF Config created: input={obj.input_dims}, output={obj.output_dims}")

# --- class: timesfm.configs.ResidualBlockConfig
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.configs import ResidualBlockConfig

# 残差ブロックの設定作成
# TODO: 用途に合わせて各パラメータを調整してください
obj = ResidualBlockConfig(
    input_dims=None  # TODO: int,  # 入力次元数
    hidden_dims=None  # TODO: int,  # 隠れ層の次元数
    output_dims=None  # TODO: int,  # 出力次元数
    use_bias=None  # TODO: bool,  # バイアス項を使用するか
    activation=None  # TODO: Literal,  # 活性化関数
)

print(f"ResidualBlock Config created: {obj.input_dims} -> {obj.hidden_dims} -> {obj.output_dims} (act={obj.activation})")

# --- class: timesfm.configs.StackedTransformersConfig
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.configs import TransformerConfig, StackedTransformersConfig

# 1. 個別のTransformer層の詳細設定
transformer_config = TransformerConfig(
    model_dims=None  # TODO: int,  # モデル次元
    hidden_dims=None  # TODO: int,  # FFNの隠れ次元
    num_heads=None  # TODO: int,  # 注意ヘッド数
    attention_norm=None  # TODO: Literal,  # Attention正規化方式
    feedforward_norm=None  # TODO: Literal,  # FFN正規化方式
    qk_norm=None  # TODO: Literal,  # QK正規化方式
    use_bias=None  # TODO: bool,  # 線形層にバイアスを使うか
    use_rotary_position_embeddings=None  # TODO: bool,  # RoPEを使用するか
    ff_activation=None  # TODO: Literal,  # FFN活性化関数
    fuse_qkv=None  # TODO: bool,  # QKVを融合実装するか
)

# 2. Transformerを積み上げる設定の作成
obj = StackedTransformersConfig(
    num_layers=None  # TODO: int,  # 積み上げるTransformer層数
    transformer=transformer_config,  # TransformerConfigオブジェクト
)

print(f"Stacked Transformers: {obj.num_layers} layers of {obj.transformer.model_dims} dims")

# --- class: timesfm.configs.TransformerConfig
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.configs import TransformerConfig

# Transformer層の設定作成
# TODO: 用途に合わせて各パラメータを調整してください
obj = TransformerConfig(
    model_dims=None  # TODO: int,  # モデル次元
    hidden_dims=None  # TODO: int,  # FFNの隠れ次元
    num_heads=None  # TODO: int,  # 注意ヘッド数
    attention_norm=None  # TODO: Literal,  # Attention正規化方式
    feedforward_norm=None  # TODO: Literal,  # FFN正規化方式
    qk_norm=None  # TODO: Literal,  # QK正規化方式
    use_bias=None  # TODO: bool,  # 線形層にバイアスを使うか
    use_rotary_position_embeddings=None  # TODO: bool,  # RoPEを使用するか
    ff_activation=None  # TODO: Literal,  # FFN活性化関数
    fuse_qkv=None  # TODO: bool,  # QKVを融合実装するか
)

print(f"TransformerConfig created: dims={obj.model_dims}, heads={obj.num_heads}")

# --- class: timesfm.flax.dense.RandomFourierFeatures
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.flax.dense import RandomFourierFeatures

obj = RandomFourierFeatures(
    args=None  # TODO: Any,
    kwargs=None  # TODO: Any,
)

# --- class: timesfm.flax.dense.ResidualBlock
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.flax.dense import ResidualBlock

obj = ResidualBlock(
    args=None  # TODO: Any,
    kwargs=None  # TODO: Any,
)

# --- class: timesfm.flax.normalization.LayerNorm
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.flax.normalization import LayerNorm

obj = LayerNorm(
    args=None  # TODO: Any,
    kwargs=None  # TODO: Any,
)

# --- class: timesfm.flax.normalization.RMSNorm
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.flax.normalization import RMSNorm

obj = RMSNorm(
    args=None  # TODO: Any,
    kwargs=None  # TODO: Any,
)

# --- class: timesfm.flax.transformer.MultiHeadAttention
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.flax.transformer import MultiHeadAttention

obj = MultiHeadAttention(
    args=None  # TODO: Any,
    kwargs=None  # TODO: Any,
)

# --- class: timesfm.flax.transformer.PerDimScale
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.flax.transformer import PerDimScale

obj = PerDimScale(
    args=None  # TODO: Any,
    kwargs=None  # TODO: Any,
)

# --- class: timesfm.flax.transformer.RotaryPositionalEmbedding
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.flax.transformer import RotaryPositionalEmbedding

obj = RotaryPositionalEmbedding(
    args=None  # TODO: Any,
    kwargs=None  # TODO: Any,
)

# --- class: timesfm.flax.transformer.Transformer
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.flax.transformer import Transformer

obj = Transformer(
    args=None  # TODO: Any,
    kwargs=None  # TODO: Any,
)

# --- class: timesfm.flax.util.DecodeCache
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.flax.util import DecodeCache

obj = DecodeCache(
    next_index=None  # TODO: Integer[jaxlib._jax.Array, 'b'],
    num_masked=None  # TODO: Integer[jaxlib._jax.Array, 'b'],
    key=None  # TODO: Float[jaxlib._jax.Array, 'b n h d'],
    value=None  # TODO: Float[jaxlib._jax.Array, 'b n h d'],
)

# --- class: timesfm.timesfm_2p5.timesfm_2p5_base.TimesFM_2p5
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.timesfm_2p5.timesfm_2p5_base import TimesFM_2p5

obj = TimesFM_2p5(
)

# --- class: timesfm.timesfm_2p5.timesfm_2p5_base.TimesFM_2p5_200M_Definition
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.timesfm_2p5.timesfm_2p5_base import TimesFM_2p5_200M_Definition

obj = TimesFM_2p5_200M_Definition(
    input_patch_len=32,
    output_patch_len=128,
    output_quantile_len=1024,
    quantiles=<factory>,
    decode_index=5,
    tokenizer=ResidualBlockConfig(input_dims=64, hidden_dims=1280, output_dims=1280, use_bias=True, activation='swish'),
    stacked_transformers=StackedTransformersConfig(num_layers=20, transformer=TransformerConfig(model_dims=1280, hidden_dims=1280, num_heads=16, attention_norm='rms', feedforward_norm='rms', qk_norm='rms', use_bias=False, use_rotary_position_embeddings=True, ff_activation='swish', fuse_qkv=True)),
    output_projection_point=ResidualBlockConfig(input_dims=1280, hidden_dims=1280, output_dims=1280, use_bias=False, activation='swish'),
    output_projection_quantiles=ResidualBlockConfig(input_dims=1280, hidden_dims=1280, output_dims=10240, use_bias=False, activation='swish'),
)

# --- class: timesfm.timesfm_2p5.timesfm_2p5_flax.TimesFM_2p5_200M_flax
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.timesfm_2p5.timesfm_2p5_flax import TimesFM_2p5_200M_flax

obj = TimesFM_2p5_200M_flax(
)

# --- class: timesfm.timesfm_2p5.timesfm_2p5_flax.TimesFM_2p5_200M_flax_module
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.timesfm_2p5.timesfm_2p5_flax import TimesFM_2p5_200M_flax_module

obj = TimesFM_2p5_200M_flax_module(
    args=None  # TODO: Any,
    kwargs=None  # TODO: Any,
)

# --- class: timesfm.timesfm_2p5.timesfm_2p5_torch.TimesFM_2p5_200M_torch
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.timesfm_2p5.timesfm_2p5_torch import TimesFM_2p5_200M_torch

obj = TimesFM_2p5_200M_torch(
    args=None  # TODO,
    kwargs=None  # TODO,
)

# --- class: timesfm.timesfm_2p5.timesfm_2p5_torch.TimesFM_2p5_200M_torch_module
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.timesfm_2p5.timesfm_2p5_torch import TimesFM_2p5_200M_torch_module

obj = TimesFM_2p5_200M_torch_module(
)

# --- class: timesfm.torch.dense.RandomFourierFeatures
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.torch.dense import RandomFourierFeatures

obj = RandomFourierFeatures(
    config=None  # TODO: RandomFourierFeaturesConfig,
)

# --- class: timesfm.torch.dense.ResidualBlock
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.torch.dense import ResidualBlock

obj = ResidualBlock(
    config=None  # TODO: ResidualBlockConfig,
)

# --- class: timesfm.torch.normalization.RMSNorm
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.torch.normalization import RMSNorm

obj = RMSNorm(
    num_features=None  # TODO: int,
    epsilon=1e-06,
)

# --- class: timesfm.torch.transformer.MultiHeadAttention
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.torch.transformer import MultiHeadAttention

obj = MultiHeadAttention(
    num_heads=None  # TODO: int,
    in_features=None  # TODO: int,
    use_per_dim_scale=True,
    use_rotary_position_embeddings=True,
    use_bias=False,
    attention_fn=<function _torch_dot_product_attention at 0x7d3dd1da79c0>,
    qk_norm='rms',
    fuse_qkv=False,
)

# --- class: timesfm.torch.transformer.PerDimScale
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.torch.transformer import PerDimScale

obj = PerDimScale(
    num_dims=None  # TODO: int,
)

# --- class: timesfm.torch.transformer.RotaryPositionalEmbedding
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.torch.transformer import RotaryPositionalEmbedding

obj = RotaryPositionalEmbedding(
    embedding_dims=None  # TODO: int,
    min_timescale=1.0,
    max_timescale=10000.0,
)

# --- class: timesfm.torch.transformer.Transformer
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.torch.transformer import Transformer

obj = Transformer(
    config=None  # TODO: TransformerConfig,
)

# --- class: timesfm.torch.util.DecodeCache
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.torch.util import DecodeCache

obj = DecodeCache(
    next_index=None  # TODO: Tensor,
    num_masked=None  # TODO: Tensor,
    key=None  # TODO: Tensor,
    value=None  # TODO: Tensor,
)

# --- class: timesfm.utils.xreg_lib.BatchedInContextXRegBase
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.utils.xreg_lib import BatchedInContextXRegBase

obj = BatchedInContextXRegBase(
    targets=None  # TODO: Sequence,
    train_lens=None  # TODO: Sequence,
    test_lens=None  # TODO: Sequence,
    train_dynamic_numerical_covariates=None,
    train_dynamic_categorical_covariates=None,
    test_dynamic_numerical_covariates=None,
    test_dynamic_categorical_covariates=None,
    static_numerical_covariates=None,
    static_categorical_covariates=None,
)

# --- class: timesfm.utils.xreg_lib.BatchedInContextXRegLinear
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.utils.xreg_lib import BatchedInContextXRegLinear

obj = BatchedInContextXRegLinear(
    targets=None  # TODO: Sequence,
    train_lens=None  # TODO: Sequence,
    test_lens=None  # TODO: Sequence,
    train_dynamic_numerical_covariates=None,
    train_dynamic_categorical_covariates=None,
    test_dynamic_numerical_covariates=None,
    test_dynamic_categorical_covariates=None,
    static_numerical_covariates=None,
    static_categorical_covariates=None,
)

# --- method: timesfm.flax.dense.RandomFourierFeatures.__init__
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.flax.dense import RandomFourierFeatures

obj = RandomFourierFeatures()  # TODO: __init__ args

result = obj.__init__(
    config=None  # TODO: RandomFourierFeaturesConfig,
    rngs=nnx.Rngs(42),
)

# --- method: timesfm.flax.dense.ResidualBlock.__init__
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.flax.dense import ResidualBlock

obj = ResidualBlock()  # TODO: __init__ args

result = obj.__init__(
    config=None  # TODO: ResidualBlockConfig,
    rngs=nnx.Rngs(42),
)

# --- method: timesfm.flax.normalization.LayerNorm.__init__
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.flax.normalization import LayerNorm

obj = LayerNorm()  # TODO: __init__ args

result = obj.__init__(
    num_features=None  # TODO: int,
    epsilon=1e-06,
    rngs=nnx.Rngs(42),
)

# --- method: timesfm.flax.normalization.RMSNorm.__init__
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.flax.normalization import RMSNorm

obj = RMSNorm()  # TODO: __init__ args

result = obj.__init__(
    num_features=None  # TODO: int,
    epsilon=1e-06,
    rngs=nnx.Rngs(42),
)

# --- method: timesfm.flax.transformer.MultiHeadAttention.__init__
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.flax.transformer import MultiHeadAttention

obj = MultiHeadAttention()  # TODO: __init__ args

result = obj.__init__(
    num_heads=None  # TODO: int,
    in_features=None  # TODO: int,
    use_per_dim_scale=True,
    use_rotary_position_embeddings=True,
    use_bias=False,
    deterministic=None,
    attention_fn=nnx.dot_product_attention,
    qk_norm='rms',
    rngs=nnx.Rngs(42),
)

# --- method: timesfm.flax.transformer.PerDimScale.__init__
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.flax.transformer import PerDimScale

obj = PerDimScale()  # TODO: __init__ args

result = obj.__init__(
    num_dims=None  # TODO: int,
    rngs=nnx.Rngs(42),
)

# --- method: timesfm.flax.transformer.RotaryPositionalEmbedding.__init__
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.flax.transformer import RotaryPositionalEmbedding

obj = RotaryPositionalEmbedding()  # TODO: __init__ args

result = obj.__init__(
    embedding_dims=None  # TODO: int,
    min_timescale=1,
    max_timescale=10000,
)

# --- method: timesfm.flax.transformer.Transformer.__init__
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.flax.transformer import Transformer

obj = Transformer()  # TODO: __init__ args

result = obj.__init__(
    config=None  # TODO: TransformerConfig,
    rngs=nnx.Rngs(42),
)

# --- method: timesfm.timesfm_2p5.timesfm_2p5_base.TimesFM_2p5.compile
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.timesfm_2p5.timesfm_2p5_base import TimesFM_2p5

obj = TimesFM_2p5()  # TODO: __init__ args

result = obj.compile(
    forecast_config=None,
)

# --- method: timesfm.timesfm_2p5.timesfm_2p5_base.TimesFM_2p5.forecast
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.timesfm_2p5.timesfm_2p5_base import TimesFM_2p5

obj = TimesFM_2p5()  # TODO: __init__ args

result = obj.forecast(
    horizon=None  # TODO: int,
    inputs=None  # TODO: list[np.ndarray],
)

# --- method: timesfm.timesfm_2p5.timesfm_2p5_base.TimesFM_2p5.forecast_with_covariates
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.timesfm_2p5.timesfm_2p5_base import TimesFM_2p5

obj = TimesFM_2p5()  # TODO: __init__ args

result = obj.forecast_with_covariates(
    inputs=None  # TODO: list[Sequence[float]],
    dynamic_numerical_covariates=None,
    dynamic_categorical_covariates=None,
    static_numerical_covariates=None,
    static_categorical_covariates=None,
    xreg_mode='xreg + timesfm',
    normalize_xreg_target_per_input=True,
    ridge=0.0,
    max_rows_per_col=0,
    force_on_cpu=False,
)

# --- method: timesfm.timesfm_2p5.timesfm_2p5_base.TimesFM_2p5.load_checkpoint
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.timesfm_2p5.timesfm_2p5_base import TimesFM_2p5

obj = TimesFM_2p5()  # TODO: __init__ args

result = obj.load_checkpoint(
    path=None  # TODO: str,
)

# --- method: timesfm.timesfm_2p5.timesfm_2p5_flax.TimesFM_2p5_200M_flax.compile
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.timesfm_2p5.timesfm_2p5_flax import TimesFM_2p5_200M_flax

obj = TimesFM_2p5_200M_flax()  # TODO: __init__ args

result = obj.compile(
    forecast_config=None  # TODO: configs.ForecastConfig,
    dryrun=True,
    kwargs=None  # TODO,
)

# --- method: timesfm.timesfm_2p5.timesfm_2p5_flax.TimesFM_2p5_200M_flax.from_pretrained
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.timesfm_2p5.timesfm_2p5_flax import TimesFM_2p5_200M_flax

obj = TimesFM_2p5_200M_flax()  # TODO: __init__ args

result = obj.from_pretrained(
    model_id='google/timesfm-2.5-200m-flax',
    revision=None,
    cache_dir=None,
    force_download=False,
    proxies=None,
    resume_download=None,
    local_files_only=None,
    token=None,
    model_kwargs=None  # TODO,
)

# --- method: timesfm.timesfm_2p5.timesfm_2p5_flax.TimesFM_2p5_200M_flax_module.__init__
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.timesfm_2p5.timesfm_2p5_flax import TimesFM_2p5_200M_flax_module

obj = TimesFM_2p5_200M_flax_module()  # TODO: __init__ args

result = obj.__init__(
)

# --- method: timesfm.timesfm_2p5.timesfm_2p5_flax.TimesFM_2p5_200M_flax_module.compile
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.timesfm_2p5.timesfm_2p5_flax import TimesFM_2p5_200M_flax_module

obj = TimesFM_2p5_200M_flax_module()  # TODO: __init__ args

result = obj.compile(
    context=None  # TODO: int,
    horizon=None  # TODO: int,
    per_core_batch_size=1,
)

# --- method: timesfm.timesfm_2p5.timesfm_2p5_flax.TimesFM_2p5_200M_flax_module.decode
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.timesfm_2p5.timesfm_2p5_flax import TimesFM_2p5_200M_flax_module

obj = TimesFM_2p5_200M_flax_module()  # TODO: __init__ args

result = obj.decode(
    horizon=None  # TODO: int,
    inputs=None  # TODO,
    masks=None  # TODO,
)

# --- method: timesfm.timesfm_2p5.timesfm_2p5_torch.TimesFM_2p5_200M_torch._from_pretrained
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.timesfm_2p5.timesfm_2p5_torch import TimesFM_2p5_200M_torch

obj = TimesFM_2p5_200M_torch()  # TODO: __init__ args

result = obj._from_pretrained(
    model_id='google/timesfm-2.5-200m-pytorch',
    revision=None  # TODO: Optional[str],
    cache_dir=None  # TODO: Optional[Union[str, Path]],
    force_download=True,
    proxies=None,
    resume_download=None,
    local_files_only=None  # TODO: bool,
    token=None  # TODO: Optional[Union[str, bool]],
    model_kwargs=None  # TODO,
)

# --- method: timesfm.timesfm_2p5.timesfm_2p5_torch.TimesFM_2p5_200M_torch._save_pretrained
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.timesfm_2p5.timesfm_2p5_torch import TimesFM_2p5_200M_torch

obj = TimesFM_2p5_200M_torch()  # TODO: __init__ args

result = obj._save_pretrained(
    save_directory=None  # TODO: Union[str, Path],
)

# --- method: timesfm.timesfm_2p5.timesfm_2p5_torch.TimesFM_2p5_200M_torch.compile
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.timesfm_2p5.timesfm_2p5_torch import TimesFM_2p5_200M_torch

obj = TimesFM_2p5_200M_torch()  # TODO: __init__ args

result = obj.compile(
    forecast_config=None  # TODO: configs.ForecastConfig,
    kwargs=None  # TODO,
)

# --- method: timesfm.timesfm_2p5.timesfm_2p5_torch.TimesFM_2p5_200M_torch_module.__init__
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.timesfm_2p5.timesfm_2p5_torch import TimesFM_2p5_200M_torch_module

obj = TimesFM_2p5_200M_torch_module()  # TODO: __init__ args

result = obj.__init__(
)

# --- method: timesfm.timesfm_2p5.timesfm_2p5_torch.TimesFM_2p5_200M_torch_module.decode
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.timesfm_2p5.timesfm_2p5_torch import TimesFM_2p5_200M_torch_module

obj = TimesFM_2p5_200M_torch_module()  # TODO: __init__ args

result = obj.decode(
    horizon=None  # TODO: int,
    inputs=None  # TODO,
    masks=None  # TODO,
)

# --- method: timesfm.timesfm_2p5.timesfm_2p5_torch.TimesFM_2p5_200M_torch_module.forecast_naive
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.timesfm_2p5.timesfm_2p5_torch import TimesFM_2p5_200M_torch_module

obj = TimesFM_2p5_200M_torch_module()  # TODO: __init__ args

result = obj.forecast_naive(
    horizon=None  # TODO: int,
    inputs=None  # TODO: Sequence[np.ndarray],
)

# --- method: timesfm.timesfm_2p5.timesfm_2p5_torch.TimesFM_2p5_200M_torch_module.forward
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.timesfm_2p5.timesfm_2p5_torch import TimesFM_2p5_200M_torch_module

obj = TimesFM_2p5_200M_torch_module()  # TODO: __init__ args

result = obj.forward(
    inputs=None  # TODO: torch.Tensor,
    masks=None  # TODO: torch.Tensor,
    decode_caches=None,
)

# --- method: timesfm.timesfm_2p5.timesfm_2p5_torch.TimesFM_2p5_200M_torch_module.load_checkpoint
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.timesfm_2p5.timesfm_2p5_torch import TimesFM_2p5_200M_torch_module

obj = TimesFM_2p5_200M_torch_module()  # TODO: __init__ args

result = obj.load_checkpoint(
    path=None  # TODO: str,
    kwargs=None  # TODO,
)

# --- method: timesfm.torch.dense.RandomFourierFeatures.__init__
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.torch.dense import RandomFourierFeatures

obj = RandomFourierFeatures()  # TODO: __init__ args

result = obj.__init__(
    config=None  # TODO: configs.RandomFourierFeaturesConfig,
)

# --- method: timesfm.torch.dense.RandomFourierFeatures.forward
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.torch.dense import RandomFourierFeatures

obj = RandomFourierFeatures()  # TODO: __init__ args

result = obj.forward(
    x=None  # TODO: torch.Tensor,
)

# --- method: timesfm.torch.dense.ResidualBlock.__init__
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.torch.dense import ResidualBlock

obj = ResidualBlock()  # TODO: __init__ args

result = obj.__init__(
    config=None  # TODO: configs.ResidualBlockConfig,
)

# --- method: timesfm.torch.dense.ResidualBlock.forward
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.torch.dense import ResidualBlock

obj = ResidualBlock()  # TODO: __init__ args

result = obj.forward(
    x=None  # TODO: torch.Tensor,
)

# --- method: timesfm.torch.normalization.RMSNorm.__init__
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.torch.normalization import RMSNorm

obj = RMSNorm()  # TODO: __init__ args

result = obj.__init__(
    num_features=None  # TODO: int,
    epsilon=1e-06,
)

# --- method: timesfm.torch.normalization.RMSNorm.forward
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.torch.normalization import RMSNorm

obj = RMSNorm()  # TODO: __init__ args

result = obj.forward(
    inputs=None  # TODO: torch.Tensor,
)

# --- method: timesfm.torch.transformer.MultiHeadAttention.__init__
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.torch.transformer import MultiHeadAttention

obj = MultiHeadAttention()  # TODO: __init__ args

result = obj.__init__(
    num_heads=None  # TODO: int,
    in_features=None  # TODO: int,
    use_per_dim_scale=True,
    use_rotary_position_embeddings=True,
    use_bias=False,
    attention_fn=_torch_dot_product_attention,
    qk_norm='rms',
    fuse_qkv=False,
)

# --- method: timesfm.torch.transformer.MultiHeadAttention.forward
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.torch.transformer import MultiHeadAttention

obj = MultiHeadAttention()  # TODO: __init__ args

result = obj.forward(
    inputs_q=None  # TODO: torch.Tensor,
    decode_cache=None,
    patch_mask=None,
)

# --- method: timesfm.torch.transformer.PerDimScale.__init__
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.torch.transformer import PerDimScale

obj = PerDimScale()  # TODO: __init__ args

result = obj.__init__(
    num_dims=None  # TODO: int,
)

# --- method: timesfm.torch.transformer.PerDimScale.forward
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.torch.transformer import PerDimScale

obj = PerDimScale()  # TODO: __init__ args

result = obj.forward(
    x=None  # TODO: torch.Tensor,
)

# --- method: timesfm.torch.transformer.RotaryPositionalEmbedding.__init__
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.torch.transformer import RotaryPositionalEmbedding

obj = RotaryPositionalEmbedding()  # TODO: __init__ args

result = obj.__init__(
    embedding_dims=None  # TODO: int,
    min_timescale=1.0,
    max_timescale=10000.0,
)

# --- method: timesfm.torch.transformer.RotaryPositionalEmbedding.forward
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.torch.transformer import RotaryPositionalEmbedding

obj = RotaryPositionalEmbedding()  # TODO: __init__ args

result = obj.forward(
    inputs=None  # TODO: torch.Tensor,
    position=None,
)

# --- method: timesfm.torch.transformer.Transformer.__init__
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.torch.transformer import Transformer

obj = Transformer()  # TODO: __init__ args

result = obj.__init__(
    config=None  # TODO: configs.TransformerConfig,
)

# --- method: timesfm.torch.transformer.Transformer.forward
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.torch.transformer import Transformer

obj = Transformer()  # TODO: __init__ args

result = obj.forward(
    input_embeddings=None  # TODO: torch.Tensor,
    patch_mask=None  # TODO: torch.Tensor,
    decode_cache=None,
)

# --- method: timesfm.utils.xreg_lib.BatchedInContextXRegBase.__init__
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.utils.xreg_lib import BatchedInContextXRegBase

obj = BatchedInContextXRegBase()  # TODO: __init__ args

result = obj.__init__(
    targets=None  # TODO: Sequence[Sequence[float]],
    train_lens=None  # TODO: Sequence[int],
    test_lens=None  # TODO: Sequence[int],
    train_dynamic_numerical_covariates=None,
    train_dynamic_categorical_covariates=None,
    test_dynamic_numerical_covariates=None,
    test_dynamic_categorical_covariates=None,
    static_numerical_covariates=None,
    static_categorical_covariates=None,
)

# --- method: timesfm.utils.xreg_lib.BatchedInContextXRegBase._assert_covariates
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.utils.xreg_lib import BatchedInContextXRegBase

obj = BatchedInContextXRegBase()  # TODO: __init__ args

result = obj._assert_covariates(
    assert_covariate_shapes=False,
)

# --- method: timesfm.utils.xreg_lib.BatchedInContextXRegBase.create_covariate_matrix
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.utils.xreg_lib import BatchedInContextXRegBase

obj = BatchedInContextXRegBase()  # TODO: __init__ args

result = obj.create_covariate_matrix(
    one_hot_encoder_drop='first',
    use_intercept=True,
    assert_covariates=False,
    assert_covariate_shapes=False,
)

# --- method: timesfm.utils.xreg_lib.BatchedInContextXRegBase.fit
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.utils.xreg_lib import BatchedInContextXRegBase

obj = BatchedInContextXRegBase()  # TODO: __init__ args

result = obj.fit(
)

# --- method: timesfm.utils.xreg_lib.BatchedInContextXRegLinear.fit
# Auto-generated call stub (CLE V6)

# NOTE: TODO のところを埋めてください

from timesfm.utils.xreg_lib import BatchedInContextXRegLinear

obj = BatchedInContextXRegLinear()  # TODO: __init__ args

result = obj.fit(
    ridge=0.0,
    one_hot_encoder_drop='first',
    use_intercept=True,
    force_on_cpu=False,
    max_rows_per_col=0,
    max_rows_per_col_sample_seed=42,
    debug_info=False,
    assert_covariates=False,
    assert_covariate_shapes=False,
)

