"""initialize current models

Revision ID: c65f580a6fa6
Revises: 
Create Date: 2026-02-07 10:25:24.747775

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID

revision = 'c65f580a6fa6'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Enums
    sa.Enum('draft', 'recommended', 'priced', 'finalized', 'ordered',
            name='build_status').create(op.get_bind())
    sa.Enum('cpu', 'cpucooler', 'motherboard', 'ram', 'storage', 'gpu', 'psu', 'case', 'fan',
            name='build_component_role').create(op.get_bind())

    # users
    op.create_table('users',
        sa.Column('id', UUID(), nullable=False),
        sa.Column('firebase_uid', sa.String(length=128), nullable=True),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('username', sa.String(length=255), nullable=True),
        sa.Column('hashed_password', sa.Text(), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('is_superuser', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_firebase_uid'), 'users', ['firebase_uid'], unique=True)

    # pc_parts
    op.create_table('pc_parts',
        sa.Column('id', UUID(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('manufacturer', sa.String(length=255), nullable=True),
        sa.Column('model_number', sa.String(length=255), nullable=True),
        sa.Column('year_released', sa.Integer(), nullable=True),
        sa.Column('part_type', sa.String(length=50), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_pc_parts_id'), 'pc_parts', ['id'], unique=False)

    # conversations
    op.create_table('conversations',
        sa.Column('id', UUID(), nullable=False),
        sa.Column('user_id', UUID(), nullable=False),
        sa.Column('build_id', UUID(), nullable=True),
        sa.Column('title', sa.String(length=255), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_conversations_id'), 'conversations', ['id'], unique=False)
    op.create_index(op.f('ix_conversations_user_id'), 'conversations', ['user_id'], unique=False)
    op.create_index(op.f('ix_conversations_build_id'), 'conversations', ['build_id'], unique=False)

    # messages
    op.create_table('messages',
        sa.Column('id', UUID(), nullable=False),
        sa.Column('conversation_id', UUID(), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('metadata', JSONB(), nullable=True, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_messages_id'), 'messages', ['id'], unique=False)
    op.create_index(op.f('ix_messages_conversation_id'), 'messages', ['conversation_id'], unique=False)

    # pc_builds
    op.create_table('pc_builds',
        sa.Column('id', UUID(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False, server_default='Untitled Build'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('owner_id', UUID(), nullable=True),
        sa.Column('status', sa.Enum('draft', 'recommended', 'priced', 'finalized', 'ordered',
                  name='build_status'), server_default='draft', nullable=False),
        sa.Column('total_price_amount', sa.Integer(), nullable=True),
        sa.Column('use_cases', ARRAY(sa.String()), nullable=True),
        sa.Column('preferences', JSONB(), nullable=True),
        sa.Column('questionnaire_answers', JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_pc_builds_id'), 'pc_builds', ['id'], unique=False)

    # Add build_id FK to conversations now that pc_builds exists
    op.create_foreign_key(
        'fk_conversations_build_id',
        'conversations', 'pc_builds',
        ['build_id'], ['id'],
        ondelete='SET NULL'
    )

    # pc_build_parts
    op.create_table('pc_build_parts',
        sa.Column('id', UUID(), nullable=False),
        sa.Column('build_id', UUID(), nullable=False),
        sa.Column('part_id', UUID(), nullable=True),
        sa.Column('role', sa.Enum('cpu', 'cpucooler', 'motherboard', 'ram', 'storage', 'gpu',
                  'psu', 'case', 'fan', name='build_component_role'), nullable=False),
        sa.Column('required_component', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('price_at_build', sa.Integer(), nullable=True),
        sa.Column('selection_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['build_id'], ['pc_builds.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['part_id'], ['pc_parts.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('build_id', 'role', name='uq_pc_build_parts_build_role')
    )
    op.create_index(op.f('ix_pc_build_parts_id'), 'pc_build_parts', ['id'], unique=False)

    # listings (polymorphic base)
    op.create_table('listings',
        sa.Column('id', UUID(), nullable=False),
        sa.Column('part_id', UUID(), nullable=False),
        sa.Column('listing_type', sa.String(length=20), nullable=False),
        sa.Column('marketplace', sa.String(length=20), nullable=False),
        sa.Column('url', sa.Text(), nullable=True),
        sa.Column('price_amount', sa.Integer(), nullable=True,
                      comment="Price in smallest currency denomination (cents, pence, etc.)"),
        sa.Column('currency', sa.String(length=3), nullable=True, server_default="USD",
                  comment="ISO 4217 currency code"),
        sa.Column('image_url', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('fetched_at', sa.DateTime(timezone=True), nullable=True,
                  comment='When this listing was last fetched from the marketplace API'),
        sa.Column('price_last_updated_at', sa.DateTime(timezone=True), nullable=True,
                  comment='When price_amount last changed'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['part_id'], ['pc_parts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_listings_id'), 'listings', ['id'], unique=False)
    op.create_index(op.f('ix_listings_part_id'), 'listings', ['part_id'], unique=False)
    op.create_index(op.f('ix_listings_marketplace'), 'listings', ['marketplace'], unique=False)

    # amazon_listings
    op.create_table('amazon_listings',
        sa.Column('id', UUID(), nullable=False),
        sa.Column('asin', sa.String(length=32), nullable=False),
        sa.Column('is_prime', sa.Boolean(), nullable=True),
        sa.Column('seller_name', sa.String(length=255), nullable=True),
        sa.Column('affiliate_tag', sa.String(length=100), nullable=True,
                  comment='Tracking ID at time of fetch'),
        sa.ForeignKeyConstraint(['id'], ['listings.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('asin', name='uq_amazon_listings_asin')
    )
    op.create_index(op.f('ix_amazon_listings_asin'), 'amazon_listings', ['asin'], unique=True)

    # ebay_listings
    op.create_table('ebay_listings',
        sa.Column('id', UUID(), nullable=False),
        sa.Column('ebay_item_id', sa.String(length=64), nullable=False),
        sa.Column('condition', sa.String(length=20), nullable=True,
                  comment='new, used, refurbished'),
        sa.Column('seller_feedback_score', sa.Integer(), nullable=True),
        sa.Column('buy_it_now', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['id'], ['listings.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('ebay_item_id', name='uq_ebay_listings_item_id')
    )
    op.create_index(op.f('ix_ebay_listings_ebay_item_id'), 'ebay_listings', ['ebay_item_id'], unique=True)

    # cpus
    op.create_table('cpus',
        sa.Column('id', UUID(), nullable=False),
        sa.Column('brand', sa.String(length=20), nullable=False),
        sa.Column('socket', sa.String(length=30), nullable=False),
        sa.Column('tdp_watts', sa.Integer(), nullable=False),
        sa.Column('has_igpu', sa.Boolean(), nullable=False),
        sa.Column('ddr_generation', ARRAY(sa.String()), nullable=False),
        sa.Column('supported_features', ARRAY(sa.String()), nullable=True),
        sa.Column('benchmark_scores', JSONB(), nullable=True),
        sa.Column('cores', sa.Integer(), nullable=False),
        sa.Column('threads', sa.Integer(), nullable=False),
        sa.Column('base_clock_ghz', sa.Float(), nullable=True),
        sa.Column('boost_clock_ghz', sa.Float(), nullable=True),
        sa.Column('l3_cache_mb', sa.Integer(), nullable=True),
        sa.Column('pcie_generation', sa.Integer(), nullable=True),
        sa.Column('max_memory_gb', sa.Integer(), nullable=True),
        sa.Column('series', sa.String(length=100), nullable=True),
        sa.ForeignKeyConstraint(['id'], ['pc_parts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # cpu_coolers
    op.create_table('cpu_coolers',
        sa.Column('id', UUID(), nullable=False),
        sa.Column('supported_sockets', ARRAY(sa.String()), nullable=False),
        sa.Column('cooler_type', sa.String(length=20), nullable=False),
        sa.Column('max_tdp_watts', sa.Integer(), nullable=True),
        sa.Column('height_mm', sa.Integer(), nullable=True),
        sa.Column('radiator_size_mm', sa.Integer(), nullable=True),
        sa.Column('fan_count', sa.Integer(), nullable=True),
        sa.Column('fan_size_mm', sa.Integer(), nullable=True),
        sa.Column('noise_dba', sa.Float(), nullable=True),
        sa.Column('has_rgb', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['id'], ['pc_parts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # motherboards
    op.create_table('motherboards',
        sa.Column('id', UUID(), nullable=False),
        sa.Column('socket', sa.String(length=30), nullable=False),
        sa.Column('form_factor', sa.String(length=10), nullable=False),
        sa.Column('ddr_generation', sa.String(length=10), nullable=False),
        sa.Column('memory_slots', sa.Integer(), nullable=False),
        sa.Column('has_wifi', sa.Boolean(), nullable=False),
        sa.Column('m2_slots', sa.Integer(), nullable=True),
        sa.Column('m2_pcie_gen', sa.Integer(), nullable=True),
        sa.Column('chipset', sa.String(length=30), nullable=True),
        sa.Column('max_memory_gb', sa.Integer(), nullable=True),
        sa.Column('sata_ports', sa.Integer(), nullable=True),
        sa.Column('pcie_x16_slots', sa.Integer(), nullable=True),
        sa.Column('pcie_generation', sa.Integer(), nullable=True),
        sa.Column('has_bluetooth', sa.Boolean(), nullable=True),
        sa.Column('usb_type_a_count', sa.Integer(), nullable=True),
        sa.Column('usb_type_c_count', sa.Integer(), nullable=True),
        sa.Column('audio_codec', sa.String(length=50), nullable=True),
        sa.ForeignKeyConstraint(['id'], ['pc_parts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # ram
    op.create_table('ram',
        sa.Column('id', UUID(), nullable=False),
        sa.Column('ddr_generation', sa.String(length=10), nullable=False),
        sa.Column('speed_mhz', sa.Integer(), nullable=False),
        sa.Column('modules', sa.Integer(), nullable=False),
        sa.Column('capacity_gb', sa.Integer(), nullable=False),
        sa.Column('height_mm', sa.Integer(), nullable=True),
        sa.Column('module_capacity_gb', sa.Integer(), nullable=True),
        sa.Column('cas_latency', sa.Integer(), nullable=True),
        sa.Column('voltage', sa.Float(), nullable=True),
        sa.Column('has_rgb', sa.Boolean(), nullable=True),
        sa.Column('is_ecc', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['id'], ['pc_parts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # storage
    op.create_table('storage',
        sa.Column('id', UUID(), nullable=False),
        sa.Column('storage_type', sa.String(length=20), nullable=False),
        sa.Column('form_factor', sa.String(length=20), nullable=False),
        sa.Column('interface', sa.String(length=20), nullable=False),
        sa.Column('capacity_gb', sa.Integer(), nullable=False),
        sa.Column('read_speed_mbps', sa.Integer(), nullable=True),
        sa.Column('write_speed_mbps', sa.Integer(), nullable=True),
        sa.Column('has_dram_cache', sa.Boolean(), nullable=True),
        sa.Column('endurance_tbw', sa.Integer(), nullable=True),
        sa.Column('rpm', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['id'], ['pc_parts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # gpus
    op.create_table('gpus',
        sa.Column('id', UUID(), nullable=False),
        sa.Column('chipset', sa.String(length=50), nullable=False),
        sa.Column('brand', sa.String(length=20), nullable=False),
        sa.Column('vram_gb', sa.Integer(), nullable=False),
        sa.Column('tdp_watts', sa.Integer(), nullable=False),
        sa.Column('length_mm', sa.Integer(), nullable=False),
        sa.Column('pcie_power_pins', sa.String(length=50), nullable=True),
        sa.Column('recommended_psu_watts', sa.Integer(), nullable=True),
        sa.Column('supported_features', ARRAY(sa.String()), nullable=True),
        sa.Column('benchmark_scores', JSONB(), nullable=True),
        sa.Column('vram_type', sa.String(length=20), nullable=True),
        sa.Column('width_slots', sa.Float(), nullable=True),
        sa.Column('pcie_generation', sa.Integer(), nullable=True),
        sa.Column('base_clock_mhz', sa.Integer(), nullable=True),
        sa.Column('boost_clock_mhz', sa.Integer(), nullable=True),
        sa.Column('has_ray_tracing', sa.Boolean(), nullable=True),
        sa.Column('cuda_cores', sa.Integer(), nullable=True),
        sa.Column('tensor_cores', sa.Integer(), nullable=True),
        sa.Column('stream_processors', sa.Integer(), nullable=True),
        sa.Column('matrix_cores', sa.Integer(), nullable=True),
        sa.Column('display_outputs', sa.Text(), nullable=True),
        sa.Column('hdmi_version', sa.Text(), nullable=True),
        sa.Column('dp_version', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['id'], ['pc_parts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # psus
    op.create_table('psus',
        sa.Column('id', UUID(), nullable=False),
        sa.Column('wattage', sa.Integer(), nullable=False),
        sa.Column('form_factor', sa.String(length=10), nullable=False),
        sa.Column('efficiency_rating', sa.String(length=30), nullable=False),
        sa.Column('pcie_8pin_connectors', sa.Integer(), nullable=True),
        sa.Column('pcie_12pin_connectors', sa.Integer(), nullable=True),
        sa.Column('pcie_16pin_connectors', sa.Integer(), nullable=True),
        sa.Column('depth_mm', sa.Integer(), nullable=True),
        sa.Column('modular', sa.String(length=10), nullable=True),
        sa.Column('eps_connectors', sa.Integer(), nullable=True),
        sa.Column('fan_size_mm', sa.Integer(), nullable=True),
        sa.Column('is_fanless', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['id'], ['pc_parts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # cases
    op.create_table('cases',
        sa.Column('id', UUID(), nullable=False),
        sa.Column('supported_mobo_form_factors', ARRAY(sa.String()), nullable=False),
        sa.Column('max_gpu_length_mm', sa.Integer(), nullable=False),
        sa.Column('max_cooler_height_mm', sa.Integer(), nullable=False),
        sa.Column('max_radiator_front_mm', sa.Integer(), nullable=True),
        sa.Column('max_radiator_top_mm', sa.Integer(), nullable=True),
        sa.Column('max_psu_length_mm', sa.Integer(), nullable=True),
        sa.Column('included_fan_count', sa.Integer(), nullable=True),
        sa.Column('chamber_count', sa.Integer(), nullable=True),
        sa.Column('front_panel_mesh', sa.Boolean(), nullable=True),
        sa.Column('color', sa.String(length=50), nullable=True),
        sa.Column('size', sa.String(length=20), nullable=False),
        sa.Column('drive_bays_35', sa.Integer(), nullable=True),
        sa.Column('drive_bays_25', sa.Integer(), nullable=True),
        sa.Column('max_fan_slots', sa.Integer(), nullable=True),
        sa.Column('has_glass_panel', sa.Boolean(), nullable=True),
        sa.Column('weight_kg', sa.Float(), nullable=True),
        sa.Column('length_mm', sa.Integer(), nullable=True),
        sa.Column('width_mm', sa.Integer(), nullable=True),
        sa.Column('height_mm', sa.Integer(), nullable=True),
        sa.Column('usb_front_type_a', sa.Integer(), nullable=True),
        sa.Column('usb_front_type_c', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['id'], ['pc_parts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # fans
    op.create_table('fans',
        sa.Column('id', UUID(), nullable=False),
        sa.Column('size_mm', sa.Integer(), nullable=False),
        sa.Column('max_rpm', sa.Integer(), nullable=True),
        sa.Column('airflow_cfm', sa.Float(), nullable=True),
        sa.Column('noise_dba', sa.Float(), nullable=True),
        sa.Column('is_pwm', sa.Boolean(), nullable=True),
        sa.Column('has_rgb', sa.Boolean(), nullable=True),
        sa.Column('bearing_type', sa.String(length=30), nullable=True),
        sa.Column('is_static_pressure', sa.Boolean(), nullable=True),
        sa.Column('pack_count', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['id'], ['pc_parts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # benchmark_types
    op.create_table('benchmark_types',
        sa.Column('id', UUID(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('slug', sa.String(length=50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('source_url', sa.Text(), nullable=True),
        sa.Column('applicable_part_types', ARRAY(sa.String()), nullable=False),
        sa.Column('higher_is_better', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
        sa.UniqueConstraint('slug')
    )
    op.create_index(op.f('ix_benchmark_types_id'), 'benchmark_types', ['id'], unique=False)

    # games
    op.create_table('games',
        sa.Column('id', UUID(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=255), nullable=False),
        sa.Column('genre', sa.String(length=50), nullable=True),
        sa.Column('store_url', sa.Text(), nullable=True),
        sa.Column('image_url', sa.Text(), nullable=True),
        sa.Column('hard_requirements', ARRAY(sa.String()), nullable=True),
        sa.Column('min_storage_gb', sa.Integer(), nullable=True),
        sa.Column('requirements_notes', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False,
                  comment='False if delisted or no longer supported'),
        sa.Column('last_verified_at', sa.DateTime(timezone=True), nullable=True,
                  comment='When specs were last manually confirmed accurate'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('title'),
        sa.UniqueConstraint('slug')
    )
    op.create_index(op.f('ix_games_id'), 'games', ['id'], unique=False)

    # game_minimum_parts
    op.create_table('game_minimum_parts',
        sa.Column('id', UUID(), nullable=False),
        sa.Column('game_id', UUID(), nullable=False),
        sa.Column('tier', sa.String(length=20), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('part_id', UUID(), nullable=True),
        sa.Column('published_name', sa.String(length=255), nullable=True),
        sa.Column('min_ram_gb', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['game_id'], ['games.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['part_id'], ['pc_parts.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('game_id', 'tier', 'role', name='uq_game_min_parts_game_tier_role')
    )
    op.create_index(op.f('ix_game_minimum_parts_id'), 'game_minimum_parts', ['id'], unique=False)
    op.create_index(op.f('ix_game_minimum_parts_game_id'), 'game_minimum_parts', ['game_id'], unique=False)

    # software
    op.create_table('software',
        sa.Column('id', UUID(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=255), nullable=False),
        sa.Column('category', sa.String(length=30), nullable=False),
        sa.Column('use_case_tags', ARRAY(sa.String()), nullable=False, server_default='{}'),
        sa.Column('developer', sa.String(length=255), nullable=True),
        sa.Column('current_version', sa.String(length=50), nullable=True),
        sa.Column('website_url', sa.Text(), nullable=True),
        sa.Column('image_url', sa.Text(), nullable=True),
        sa.Column('is_free', sa.Boolean(), nullable=True),
        sa.Column('platform_requirements', ARRAY(sa.String()), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
        sa.UniqueConstraint('slug')
    )
    op.create_index(op.f('ix_software_id'), 'software', ['id'], unique=False)

    # software_tiers
    op.create_table('software_tiers',
        sa.Column('id', UUID(), nullable=False),
        sa.Column('software_id', UUID(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('slug', sa.String(length=100), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('gpu_importance', sa.String(length=20), nullable=False, server_default='optional'),
        sa.Column('min_ram_gb', sa.Integer(), nullable=True),
        sa.Column('recommended_ram_gb', sa.Integer(), nullable=True),
        sa.Column('min_vram_gb', sa.Integer(), nullable=True),
        sa.Column('min_storage_gb', sa.Integer(), nullable=True),
        sa.Column('min_cores', sa.Integer(), nullable=True),
        sa.Column('prefers_single_thread', sa.Boolean(), nullable=True),
        sa.Column('extra_requirements', JSONB(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['software_id'], ['software.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('software_id', 'slug', name='uq_software_tiers_software_slug')
    )
    op.create_index(op.f('ix_software_tiers_id'), 'software_tiers', ['id'], unique=False)
    op.create_index(op.f('ix_software_tiers_software_id'), 'software_tiers', ['software_id'], unique=False)

    # software_minimum_parts
    op.create_table('software_minimum_parts',
        sa.Column('id', UUID(), nullable=False),
        sa.Column('tier_id', UUID(), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('part_id', UUID(), nullable=True),
        sa.Column('published_name', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['tier_id'], ['software_tiers.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['part_id'], ['pc_parts.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tier_id', 'role', name='uq_software_min_parts_tier_role')
    )
    op.create_index(op.f('ix_software_minimum_parts_id'), 'software_minimum_parts', ['id'], unique=False)
    op.create_index(op.f('ix_software_minimum_parts_tier_id'), 'software_minimum_parts', ['tier_id'], unique=False)

    # reference_builds
    op.create_table('reference_builds',
        sa.Column('id', UUID(), nullable=False),
        sa.Column('build_key', sa.String(length=64), nullable=False),
        sa.Column('label', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('total_approx', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('build_key')
    )
    op.create_index(op.f('ix_reference_builds_id'), 'reference_builds', ['id'], unique=False)
    op.create_index(op.f('ix_reference_builds_build_key'), 'reference_builds', ['build_key'], unique=True)

    # reference_build_parts
    op.create_table('reference_build_parts',
        sa.Column('id', UUID(), nullable=False),
        sa.Column('build_id', UUID(), nullable=False),
        sa.Column('part_id', UUID(), nullable=False),
        sa.Column('component', sa.String(length=50), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=False),
        sa.Column('approx_price', sa.Integer(), nullable=False),
        sa.Column('approx_price_updated_at', sa.DateTime(timezone=True), nullable=True,
                  comment='When approx_price was last manually reviewed or updated'),
        sa.ForeignKeyConstraint(['build_id'], ['reference_builds.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['part_id'], ['pc_parts.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_reference_build_parts_id'), 'reference_build_parts', ['id'], unique=False)
    op.create_index(op.f('ix_reference_build_parts_build_id'), 'reference_build_parts', ['build_id'], unique=False)
    op.create_index(op.f('ix_reference_build_parts_part_id'), 'reference_build_parts', ['part_id'], unique=False)


def downgrade():
    op.drop_table('reference_build_parts')
    op.drop_table('reference_builds')
    op.drop_table('software_minimum_parts')
    op.drop_table('software_tiers')
    op.drop_table('software')
    op.drop_table('game_minimum_parts')
    op.drop_table('games')
    op.drop_table('benchmark_types')
    op.drop_table('fans')
    op.drop_table('cases')
    op.drop_table('psus')
    op.drop_table('gpus')
    op.drop_table('storage')
    op.drop_table('ram')
    op.drop_table('motherboards')
    op.drop_table('cpu_coolers')
    op.drop_table('cpus')
    op.drop_table('ebay_listings')
    op.drop_table('amazon_listings')
    op.drop_table('listings')
    op.drop_table('pc_build_parts')
    op.drop_table('pc_builds')
    op.drop_table('messages')
    op.drop_constraint('fk_conversations_build_id', 'conversations', type_='foreignkey')
    op.drop_table('conversations')
    op.drop_table('pc_parts')
    op.drop_table('users')
    sa.Enum(name='build_component_role').drop(op.get_bind())
    sa.Enum(name='build_status').drop(op.get_bind())
