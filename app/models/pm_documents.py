from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Enum as SQLEnum

from app.core.database import Base
from app.models.enums import DocumentType


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        Index("idx_documents_owner_id", "owner_id"),
        Index("idx_documents_user_id", "user_id"),
        Index("idx_documents_property_id", "property_id"),
        Index("idx_documents_lease_id", "lease_id"),
        Index("idx_documents_maintenance_request_id", "maintenance_request_id"),
        Index("idx_documents_rental_application_id", "rental_application_id"),
        Index("idx_documents_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    # Portfolio owner / landlord who owns the resource context
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    # Optional user the doc is about (KYC docs for owner/tenant/applicant/etc.)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    property_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("properties.id", ondelete="SET NULL"), nullable=True
    )
    lease_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("leases.id", ondelete="SET NULL"), nullable=True
    )
    maintenance_request_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("maintenance_requests.id", ondelete="SET NULL"), nullable=True
    )
    rental_application_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("rental_applications.id", ondelete="SET NULL"), nullable=True
    )

    document_type: Mapped[DocumentType] = mapped_column(
        SQLEnum(DocumentType, name="document_type"), nullable=False
    )
    title: Mapped[str] = mapped_column(String, nullable=False)

    # Storage metadata
    file_url: Mapped[str] = mapped_column(Text, nullable=False)
    file_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    mime_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    file_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    shared_with_tenant: Mapped[bool] = mapped_column(Boolean, default=False)
    shared_with_agent: Mapped[bool] = mapped_column(Boolean, default=False)

    version: Mapped[int] = mapped_column(Integer, default=1)
    replaces_document_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )

    created_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )

    # Relationships
    owner: Mapped["User"] = relationship("User", foreign_keys=[owner_id])
    user: Mapped[Optional["User"]] = relationship("User", foreign_keys=[user_id])
    created_by: Mapped[Optional["User"]] = relationship("User", foreign_keys=[created_by_user_id])

    property: Mapped[Optional["Property"]] = relationship("Property", back_populates="documents")
    lease: Mapped[Optional["Lease"]] = relationship("Lease", foreign_keys=[lease_id])
    maintenance_request: Mapped[Optional["MaintenanceRequest"]] = relationship(
        "MaintenanceRequest", back_populates="documents"
    )
    rental_application: Mapped[Optional["RentalApplication"]] = relationship(
        "RentalApplication", back_populates="documents"
    )

    replaces: Mapped[Optional["Document"]] = relationship("Document", remote_side=[id])

