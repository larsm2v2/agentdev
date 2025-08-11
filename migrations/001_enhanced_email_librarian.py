"""
Database migration script using Alembic
Run: alembic revision --autogenerate -m "Create enhanced email librarian tables"
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid

# revision identifiers
revision = '001_enhanced_email_librarian'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Create email_processing_jobs table
    op.create_table('email_processing_jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=uuid.uuid4),
        sa.Column('job_type', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, default='pending'),
        sa.Column('config', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, default=sa.func.now()),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('result', sa.JSON(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('processed_count', sa.Integer(), nullable=False, default=0),
        sa.Column('total_count', sa.Integer(), nullable=False, default=0),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create email_vectors table
    op.create_table('email_vectors',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=uuid.uuid4),
        sa.Column('email_id', sa.String(length=255), nullable=False),
        sa.Column('subject', sa.Text(), nullable=False),
        sa.Column('sender', sa.String(length=255), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('category', sa.String(length=100), nullable=True),
        sa.Column('labels', sa.JSON(), nullable=True),
        sa.Column('vector_id', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email_id')
    )
    
    # Create agent_executions table
    op.create_table('agent_executions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=uuid.uuid4),
        sa.Column('agent_name', sa.String(length=100), nullable=False),
        sa.Column('task_description', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, default='running'),
        sa.Column('started_at', sa.DateTime(), nullable=False, default=sa.func.now()),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('result', sa.JSON(), nullable=True),
        sa.Column('langfuse_trace_id', sa.String(length=255), nullable=True),
        sa.Column('n8n_workflow_id', sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index('idx_email_processing_jobs_status', 'email_processing_jobs', ['status'])
    op.create_index('idx_email_processing_jobs_type', 'email_processing_jobs', ['job_type'])
    op.create_index('idx_email_processing_jobs_created', 'email_processing_jobs', ['created_at'])
    
    op.create_index('idx_email_vectors_email_id', 'email_vectors', ['email_id'])
    op.create_index('idx_email_vectors_category', 'email_vectors', ['category'])
    op.create_index('idx_email_vectors_timestamp', 'email_vectors', ['timestamp'])
    
    op.create_index('idx_agent_executions_status', 'agent_executions', ['status'])
    op.create_index('idx_agent_executions_agent', 'agent_executions', ['agent_name'])

def downgrade():
    op.drop_table('agent_executions')
    op.drop_table('email_vectors')
    op.drop_table('email_processing_jobs')
