import type { IconName } from './Icon'

export interface SourceRow {
  title: string
  url: string
  takeaway?: string
  passages: { id: string; quote: string; note?: string }[]
}

export interface Example {
  id: string
  claim: string
  icon: IconName
  verdict: 'true' | 'false'
  summary: { text: string; cites: number[] }[]
  pages: SourceRow[]
}

function page(title: string, url: string, quote: string, takeaway: string): SourceRow {
  return { title, url, takeaway, passages: [{ id: url, quote }] }
}

export const examples: Example[] = [
  {
    id: 'venus', claim: 'Venus is closest to the Sun', icon: 'planet', verdict: 'false',
    summary: [
      { text: 'Mercury follows the innermost orbit around the Sun.', cites: [1, 2] },
      { text: 'Venus follows the next orbit out, making it the second planet from the Sun.', cites: [3] },
    ],
    pages: [
      page('Mercury', 'https://science.nasa.gov/mercury/', 'Mercury is the closest planet to the Sun, and the smallest planet in our solar system.', 'Of all the planets in our solar system, Mercury orbits closest to the Sun.'),
      page('About the Planets', 'https://science.nasa.gov/solar-system/planets/', 'The first four planets from the Sun are Mercury, Venus, Earth, and Mars.', 'Moving outward from the Sun, Mercury comes first, followed by Venus, Earth, and Mars.'),
      page('Venus', 'https://science.nasa.gov/venus/', 'Venus is the second planet from the Sun, and the sixth largest planet.', 'Venus occupies the second orbit around the Sun, one position beyond Mercury.'),
    ],
  },
  {
    id: 'octopuses', claim: 'Octopuses have three hearts', icon: 'heart', verdict: 'true',
    summary: [
      { text: 'An octopus has three hearts that share the work of circulating blood.', cites: [1, 2] },
      { text: 'Two send blood to the gills to pick up oxygen, and the third delivers it to the body.', cites: [3] },
    ],
    pages: [
      page('Giant Pacific octopus', 'https://www.sheddaquarium.org/animals/octopus', 'Octopuses have three hearts: two to pump blood through the gills and one to circulate it to the organs.', 'Two octopus hearts supply the gills, while the third circulates blood to the organs.'),
      page('The ABCs of Cephalopods', 'https://www.amnh.org/explore/videos/kid-science/abcs-cephalopods-conservation-biologist-samantha-cheng', 'They have three hearts…', 'The museum identifies three hearts as a feature of octopus anatomy.'),
      page('Cephalopods', 'https://ocean.si.edu/ocean-life/invertebrates/octopuses-squids-and-relatives', 'The two branchial hearts push oxygen-depleted blood through the gills while the systemic heart pumps the oxygenated blood throughout the body.', 'Blood gains oxygen at the gills before the systemic heart supplies the body.'),
    ],
  },
  {
    id: 'sound', claim: 'Sound travels in a vacuum', icon: 'wave', verdict: 'false',
    summary: [
      { text: 'Sound travels when a vibration passes between particles in a material.', cites: [1, 2] },
      { text: 'A vacuum contains no particles to carry that vibration.', cites: [3] },
    ],
    pages: [
      page('Anatomy of an Electromagnetic Wave', 'https://science.nasa.gov/ems/02_anatomy/', 'Sound waves cannot travel in the vacuum of space because there is no medium to transmit these mechanical waves.', 'Sound needs a material to carry vibrations, which a vacuum cannot provide.'),
      page('Production of Electromagnetic Waves', 'https://openstax.org/books/college-physics-ap-courses/pages/24-2-production-of-electromagnetic-waves', 'Similarly, sound waves travel by molecules colliding with their neighbors. If there is no matter, sound waves cannot travel.', 'Sound spreads through collisions between neighboring molecules, a process that requires matter.'),
      page('Sound Is a Mechanical Wave', 'https://www.physicsclassroom.com/getattachment/Physics-Video-Tutorial/Sound-Waves/Sound-is-a-Mechanical-Wave/Lecture-Notes/LessonNotes.pdf?lang=en-US', 'Sound waves are mechanical waves that cannot travel through a vacuum.', 'As a mechanical wave, sound needs a physical medium to travel.'),
    ],
  },
]
