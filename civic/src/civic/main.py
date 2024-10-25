#!/usr/bin/env python
from civic.crew import CivicCrew


def run():
    topic = input("Please enter the topic: ")
    inputs = {
        'topic': topic
    }
    CivicCrew().crew().kickoff(inputs=inputs)