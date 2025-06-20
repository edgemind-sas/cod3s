import Pycatshoo as pyc
import pydantic
import numpy as np
import pandas as pd
import plotly.express as px
import typing
from .automaton import PycTransition
from ..core import ObjCOD3S


class PycSequence(ObjCOD3S):
    # Parametres
    probability: float = pydantic.Field(None, description="Sequence probability")

    nb_occurrences: int = pydantic.Field(None, description="Sequence occurrence number")

    target_event: str = pydantic.Field(None, description="Target event")

    transitions: typing.List[PycTransition] = pydantic.Field(
        [], description="Liste de transition"
    )


# Parser
# import xml.etree.ElementTree as ET
# from pyc_sequences import *


# # Read Sequences
# def parse_sequences(xml_file_path):
#     sequences_list = []

#     tree = ET.parse(xml_file_path)
#     root = tree.getroot()
#     for seq in root.findall("SEQ"):
#         probability = seq.get('P')
#         number_instance = seq.get('N')
#         endCause = None

#         transitions = []
#         for branch in seq.findall("BR"):
#             branch_time = seq.get('T')
#             for branch_tr in branch.findall("TR"):
#                 tr_name = branch_tr.get('NAME')
#                 tr_final_state = branch_tr.get('ST')
#                 tr_law = branch_tr.get('TD')
#                 transition = create_transition(tr_name, tr_final_state, branch_time, tr_law)
#                 transitions.append(transition)

#                 endCause = tr_final_state

#         sequence = create_sequence(probability, number_instance, endCause, transitions)
#         sequences_list.append(sequence)

#     return sequences_list


# def create_transition(name, state, time, law):
#     transition = TransitionModel(name=name,
#                                       state=state,
#                                       time=time,
#                                       law=law)
#     return transition


# def create_sequence(probability, nb_occurrences, target_event, transitions):
#     sequence = SequenceModel(probability=probability,
#                                       nb_occurrences=nb_occurrences,
#                                       target_event=target_event)

#     for transition in transitions:
#         sequence.transitions.append(transition)

#     return sequence
