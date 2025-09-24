package com.ba.bluearchivemusicapi.entities;

import jakarta.persistence.*;
import lombok.*;

@Setter
@Getter
@AllArgsConstructor
@NoArgsConstructor
@Entity
@Builder
@Table(name = "OST")
public class OST {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "ost_number")
    private Integer ostNumber;

    @Column(name = "name")
    private String name;

    @Column(name = "author")
    private String author;

    @Column(name = "image_path")
    private String image_path;

    @Column(name = "audio_path")
    private String audio_path;

    @Column(name = "play_count")
    private Integer playCount;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "ost_type_id")
    private OstType ostType;
}
