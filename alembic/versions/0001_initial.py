"""initial tables

Revision ID: 0001_initial
Revises:
Create Date: 2026-03-16 00:00:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    document_type = sa.Enum('SOP', 'LOG', name='document_type')
    document_status = sa.Enum('draft', 'approved', name='document_status')
    session_status = sa.Enum('active', 'closed', name='session_status')

    document_type.create(op.get_bind(), checkfirst=True)
    document_status.create(op.get_bind(), checkfirst=True)
    session_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        'documents',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('type', document_type, nullable=False),
        sa.Column('original_filename', sa.String(length=255), nullable=False),
        sa.Column('storage_path', sa.String(length=512), nullable=False),
        sa.Column('raw_text', sa.Text(), nullable=False),
        sa.Column('extracted_json', sa.JSON(), nullable=True),
        sa.Column('approved_json', sa.JSON(), nullable=True),
        sa.Column('status', document_status, nullable=False, server_default='draft'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_documents_id', 'documents', ['id'])
    op.create_index('ix_documents_type', 'documents', ['type'])
    op.create_index('ix_documents_status', 'documents', ['status'])
    op.create_index('ix_documents_type_status', 'documents', ['type', 'status'])

    op.create_table(
        'review_sessions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('document_id', sa.Integer(), sa.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('selected_parameters', sa.JSON(), nullable=True),
        sa.Column('session_status', session_status, nullable=False, server_default='active'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_review_sessions_id', 'review_sessions', ['id'])
    op.create_index('ix_review_sessions_document_id', 'review_sessions', ['document_id'])

    op.create_table(
        'assistant_messages',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(
            'review_session_id',
            sa.Integer(),
            sa.ForeignKey('review_sessions.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('updated_json_snapshot', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_assistant_messages_id', 'assistant_messages', ['id'])
    op.create_index('ix_assistant_messages_review_session_id', 'assistant_messages', ['review_session_id'])

    op.create_table(
        'analyses',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('sop_document_id', sa.Integer(), sa.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('log_document_id', sa.Integer(), sa.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('result_json', sa.JSON(), nullable=False),
        sa.Column('summary_json', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_analyses_id', 'analyses', ['id'])
    op.create_index('ix_analyses_sop_document_id', 'analyses', ['sop_document_id'])
    op.create_index('ix_analyses_log_document_id', 'analyses', ['log_document_id'])
    op.create_index('ix_analyses_sop_log', 'analyses', ['sop_document_id', 'log_document_id'])


def downgrade() -> None:
    op.drop_index('ix_analyses_sop_log', table_name='analyses')
    op.drop_index('ix_analyses_log_document_id', table_name='analyses')
    op.drop_index('ix_analyses_sop_document_id', table_name='analyses')
    op.drop_index('ix_analyses_id', table_name='analyses')
    op.drop_table('analyses')

    op.drop_index('ix_assistant_messages_review_session_id', table_name='assistant_messages')
    op.drop_index('ix_assistant_messages_id', table_name='assistant_messages')
    op.drop_table('assistant_messages')

    op.drop_index('ix_review_sessions_document_id', table_name='review_sessions')
    op.drop_index('ix_review_sessions_id', table_name='review_sessions')
    op.drop_table('review_sessions')

    op.drop_index('ix_documents_type_status', table_name='documents')
    op.drop_index('ix_documents_status', table_name='documents')
    op.drop_index('ix_documents_type', table_name='documents')
    op.drop_index('ix_documents_id', table_name='documents')
    op.drop_table('documents')

    sa.Enum(name='session_status').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='document_status').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='document_type').drop(op.get_bind(), checkfirst=True)
