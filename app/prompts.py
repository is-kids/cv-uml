"""Prompts for LLM inference."""

# Prompt for extracting steps from diagram images
IMAGE_PROMPT = """Analyze this diagram image and extract all steps/actions shown.

Output a JSON object with this structure:
{
  "diagram_type": "sequence|flowchart|activity|state|class|other",
  "steps": [
    {
      "number": 1,
      "actor": "actor name or null",
      "action": "description of action",
      "target": "target of action or null",
      "note": "additional notes or null"
    }
  ],
  "confidence": 0.0-1.0
}

Rules:
1. Number steps sequentially starting from 1
2. For sequence diagrams: actor is the sender, target is the receiver
3. For flowcharts: actor can be the shape type (decision, process, etc.)
4. Include ALL visible steps, arrows, and connections
5. Read text labels carefully
6. Set confidence based on clarity of the diagram

Return ONLY valid JSON, no other text."""


# Prompt for extracting steps from text-based diagram formats (DrawIO XML, BPMN)
TEXT_PROMPT = """Analyze this diagram definition and extract all steps/actions.

Output a JSON object with this structure:
{
  "diagram_type": "sequence|flowchart|activity|state|bpmn|other",
  "steps": [
    {
      "number": 1,
      "actor": "actor/participant name or null",
      "action": "description of action/task",
      "target": "target or null",
      "note": "additional notes or null"
    }
  ],
  "confidence": 0.0-1.0
}

Rules:
1. Parse element names, labels, and values
2. Follow connections/edges to determine step order
3. Include participants, tasks, gateways, events
4. For BPMN: extract startEvent, tasks, gateways, endEvent
5. For DrawIO: extract mxCell labels and connections

Return ONLY valid JSON, no other text."""


# Prompt for generating PlantUML from steps
PLANTUML_SEQUENCE_PROMPT = """Convert these steps to PlantUML sequence diagram syntax.

Steps:
{steps}

Output valid PlantUML code starting with @startuml and ending with @enduml.
Use proper sequence diagram syntax with -> arrows.
Include all actors/participants mentioned in the steps."""


PLANTUML_ACTIVITY_PROMPT = """Convert these steps to PlantUML activity diagram syntax.

Steps:
{steps}

Output valid PlantUML code starting with @startuml and ending with @enduml.
Use proper activity diagram syntax with :action; format.
Include decision points if implied by the steps."""


# Simplified prompts for when full JSON parsing fails
SIMPLE_IMAGE_PROMPT = """List all steps shown in this diagram, one per line.
Format each line as: [number]. [actor] -> [action] -> [target]
If actor or target is unclear, use "?"
Example:
1. User -> clicks login button -> System
2. System -> validates credentials -> Database"""


SIMPLE_TEXT_PROMPT = """List all steps/actions from this diagram definition, one per line.
Format each line as: [number]. [actor] -> [action] -> [target]
If actor or target is unclear, use "?"
Example:
1. User -> submits form -> Server
2. Server -> saves data -> Database"""
