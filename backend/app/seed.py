"""Explicit, idempotent fictional records only. No synthetic movement seeded."""

import os

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Access, Assignment, Exercise, Patient, User
from app.schemas.api import ExerciseConfig
from app.services.security import password_hash


def seed():
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.email == "therapist@demo.local")):
            return
        therapist = User(
            email="therapist@demo.local",
            name="Dr. Avery Demo",
            role="therapist",
            password_hash=password_hash(os.getenv("DEMO_PASSWORD", "DemoTherapist123!")),
        )
        patient_user = User(
            email="patient@demo.local",
            name="Jordan Sample",
            role="patient",
            password_hash=password_hash(os.getenv("DEMO_PASSWORD", "DemoPatient123!")),
        )
        db.add_all([therapist, patient_user])
        db.flush()
        patient = Patient(
            user_id=patient_user.id,
            name="Jordan Sample",
            is_fictional=True,
            notes="Fictional demo patient. No medical history or treatment claims.",
        )
        exercise = Exercise(
            name="Seated reach",
            description="A configurable reach-and-return demonstration. Phone mode measures projected right-elbow extension. Quest mode measures hand-to-target distance in Quest coordinates.",
            config=ExerciseConfig().model_dump(),
        )
        db.add_all([patient, exercise])
        db.flush()
        db.add(Access(therapist_id=therapist.id, patient_id=patient.id))
        db.add(
            Assignment(
                patient_id=patient.id,
                therapist_id=therapist.id,
                exercise_definition_id=exercise.id,
                repetitions=5,
                config=exercise.config,
            )
        )
        db.commit()


if __name__ == "__main__":
    seed()
